from can_message import DataFrame, ErrorFrame, RemoteFrame, OverloadFrame
from can_error_handler import CANErrorHandler
import time
import random

TRANSMITTING = "transmitting"
RECEIVING = "receiving"
WAITING = "waiting"
BUS_OFF = "Bus Off"
ERROR_PASSIVE = "Error Passive"
ERROR_ACTIVE = "Error Active"


class CANNode:
    def __init__(self, node_id, bus=None, produced_ids=None, filters=None,
                 message_interval=0.025, node_comp="None"):
        self.node_id = node_id
        self.bus = bus
        self.message_interval = message_interval
        self.last_transmission_time = 0
        self.message_queue = []
        self.produced_ids = produced_ids if produced_ids else list(range(0, 2048))
        self.filters = filters if filters else list(range(0, 2048))
        self.state = ERROR_ACTIVE
        self.mode = WAITING
        self.transmit_error_counter = 0
        self.receive_error_counter = 0
        self.current_bit_index = 0
        self.node_comp = node_comp

        self.error_handler = CANErrorHandler()

    def set_bus(self, bus):
        self.bus = bus

    def has_pending_message(self):
        return len(self.message_queue) > 0

    def add_message_to_queue(self, message):
        self.message_queue.append(message)

    def set_component(self, node_comp):
        self.node_comp = node_comp

    def is_transmission_complete(self):
        if not self.has_pending_message():
            print(f"Node {self.node_id} has no pending message.")
            return True
        msg = self.message_queue[0]
        bitstream = msg.get_bitstream()
        return (self.current_bit_index >= len(bitstream))

    def send_message(self, message_id=None, data=None, frame_type="data", error_type=None, interactive=False):
        if self.state == BUS_OFF:
            print(f"Node {self.node_id} is in BUS_OFF state and cannot transmit.")
            return

        frame_type_lower = frame_type.lower()
        if frame_type_lower == "data":
            msg = DataFrame(message_id, self.node_id, data)
        elif frame_type_lower == "remote":
            msg = RemoteFrame(message_id, self.node_id)
        elif frame_type_lower == "error":
            msg = ErrorFrame(sent_by=self.node_id)
        elif frame_type_lower == "overload":
            msg = OverloadFrame(sent_by=self.node_id)
        else:
            print("Invalid frame type specified.")
            return

        # Optional forced error injection
        if error_type:
            print(f"Injecting {error_type} error into message.")
            self.error_handler.inject_error(error_type, msg)
        elif interactive and random.random() < 0.1:
            # 10% chance of random error
            random_err = random.choice(["bit_error","stuff_error","crc_error","ack_error","form_error"])
            print(f"Randomly injecting {random_err} error into message.")
            self.error_handler.inject_error(random_err, msg)

        self.message_queue.append(msg)
        self.mode = TRANSMITTING

    def transmit_bit(self):
        """
        Return exactly one bit from the front message, if any.
        If node is BUS_OFF, or no bits => None.
        If forced bit_error => broadcast error frame, stop.
        """
        if self.state == BUS_OFF:
            return None

        if not self.has_pending_message():
            return None

        msg = self.message_queue[0]
        bs = msg.get_bitstream()
        if self.current_bit_index < len(bs):
            transmitted_bit = bs[self.current_bit_index]
            # Check for forced bit_error
            if (self.mode == TRANSMITTING 
                and not self.bus.in_arbitration
                and msg.error_type == "bit_error"
                and self.current_bit_index == msg.error_bit_index):
                print(f"Node {self.node_id}: forced bit_error at bit {self.current_bit_index}")
                self.bus.broadcast_error_frame("bit_error", msg)
                self.stop_transmitting()
                self.current_bit_index = 0
                return None

            self.current_bit_index += 1
            return transmitted_bit
        return None

    def receive_message(self, message):
        """
        Called after arbitration if the node is a receiver of the final message.
        If node is BUS_OFF => we do nothing.
        If ID not in filters => ignore.
        If there's an error => broadcast error frame
        else => normal ACK
        """
        if self.state == BUS_OFF:
            return

        if message.identifier not in self.filters:
            print(f"Node {self.node_id} ignored message with ID {message.identifier}.")
        else:
            print(f"Node {self.node_id} received message with ID {message.identifier}.")

        # Check error_type in message
        if message.error_type == "stuff_error":
            print(f"Node {self.node_id} => detected a Bit Stuffing Error.")
            self.bus.broadcast_error_frame("stuff_error", message)
            return False
        elif message.error_type == "crc_error":
            print(f"Node {self.node_id} => detected a CRC Error.")
            self.bus.broadcast_error_frame("crc_error", message)
            return False
        elif message.error_type == "form_error":
            print(f"Node {self.node_id} => detected a Form Error.")
            self.bus.broadcast_error_frame("form_error", message)
            return False
        elif message.error_type == "ack_error":
            return False

        # no error in the msg => ack
        message.update_ack()
        print(f"Node {self.node_id} => sent an ACK bit.")
        return True

    def process_received_bit(self, message, winner_node):
        if self.state == BUS_OFF:
            return True
        if self.mode != RECEIVING:
            return True

        current_bit_index = winner_node.current_bit_index - 1
        if message.error_type == "ack_error" and current_bit_index == message.error_bit_index:
            print(f"Node {self.node_id} => detected ack_error at bit {current_bit_index}")
            self.bus.broadcast_error_frame("ack_error", message)
            return False
        if message.error_type == "stuff_error" and current_bit_index == message.error_bit_index:
            print(f"Node {self.node_id} => detected stuff_error at bit {current_bit_index}")
            self.bus.broadcast_error_frame("stuff_error", message)
            return False
        if message.error_type == "crc_error" and current_bit_index == message.error_bit_index:
            print(f"Node {self.node_id} => detected crc_error at bit {current_bit_index}")
            self.bus.broadcast_error_frame("crc_error", message)
            return False
        if message.error_type == "form_error" and current_bit_index == message.error_bit_index:
            print(f"Node {self.node_id} => detected form_error at bit {current_bit_index}")
            self.bus.broadcast_error_frame("form_error", message)
            return False

        return True

    def detect_and_handle_error(self, message):
        """
        Called if the bus tries to see if there's an error in the message
        or if we want to detect error. Usually the bus calls broadcast_error_frame 
        if it sees message.error_type != None, etc.
        """
        if self.error_handler.detect_error(message.error_type, message):
            self.bus.broadcast_error_frame(message.error_type, message)
            return True
        return False

    def handle_overload_frame(self):
        # Overload frames => typically 6 dominant bits, etc. 
        # We'll just simulate a short delay
        time.sleep(0.1)

    def handle_error_frame(self, error_type):
        """
        If the bus broadcasts an error frame => all non-bus-off nodes 
        increment TE or RE depending on mode.
        """
        if self.state == BUS_OFF:
            return
        if self.mode == TRANSMITTING:
            print(f"Node {self.node_id} => error_frame as transmitter => increment TEC.")
            self.increment_transmit_error()
        elif self.mode == RECEIVING:
            print(f"Node {self.node_id} => error_frame as receiver => increment REC.")
            self.increment_receive_error()

    def retransmit_message(self):
        if self.state == BUS_OFF:
            print(f"Node {self.node_id} => bus_off => cannot retransmit.")
            self.message_queue.clear()
            return

        if self.has_pending_message():
            self.current_bit_index = 0
            self.mode = TRANSMITTING

    def stop_transmitting(self):
        self.mode = WAITING
        self.current_bit_index = 0

    def increment_transmit_error(self):
        self.transmit_error_counter += 8
        self.check_state_transition()
        self.mode = WAITING

    def increment_receive_error(self):
        self.receive_error_counter += 1
        self.check_state_transition()

    def decrement_transmit_error(self):
        if self.transmit_error_counter > 0:
            self.transmit_error_counter -= 1
        self.check_state_transition()

    def decrement_receive_error(self):
        if self.receive_error_counter > 0:
            self.receive_error_counter -= 1
        self.check_state_transition()

    def check_state_transition(self):
        if self.transmit_error_counter >= 255 or self.receive_error_counter >= 255:
            if self.state != BUS_OFF:
                print(f"Node {self.node_id} => enters BUS_OFF state.")
            self.state = BUS_OFF 
        elif self.transmit_error_counter >= 127 or self.receive_error_counter >= 127:
            if self.state != ERROR_PASSIVE:
                print(f"Node {self.node_id} => enters ERROR_PASSIVE state.")
            self.state = ERROR_PASSIVE
        else:
            if self.state != ERROR_ACTIVE:
                print(f"Node {self.node_id} => enters ERROR_ACTIVE state.")
            self.state = ERROR_ACTIVE

    def reset_node(self):
        self.transmit_error_counter = 0
        self.receive_error_counter = 0
        self.state = ERROR_ACTIVE
        self.mode = WAITING
        self.current_bit_index = 0
