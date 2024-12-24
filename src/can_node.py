# can_node.py
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
    def __init__(self, node_id, bus=None, produced_ids=None, filters=None, message_interval=0.025, node_comp="None"):
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

    def add_message_to_queue(self, message):
        self.message_queue.append(message)

    def is_transmission_complete(self):
        if not self.has_pending_message():
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
            message = DataFrame(message_id, self.node_id, data)
        elif frame_type_lower == "remote":
            message = RemoteFrame(message_id, self.node_id)
        elif frame_type_lower == "error":
            message = ErrorFrame(sent_by=self.node_id)
        elif frame_type_lower == "overload":
            message = OverloadFrame(sent_by=self.node_id)
        else:
            print("Invalid frame type specified.")
            return

        if error_type:
            print(f"Injecting {error_type} error into message.")
            self.error_handler.inject_error(error_type, message)
        elif interactive and random.random() < 0.1: 
            random_error = random.choice(["bit_error", "stuff_error", "crc_error", "ack_error", "form_error"])
            print(f"Randomly injecting {random_error} error into message.")
            self.error_handler.inject_error(random_error, message)

        self.add_message_to_queue(message)
        self.mode = TRANSMITTING 

    def transmit_bit(self):
        if not self.has_pending_message():
            return

        message = self.message_queue[0]
        bitstream = message.get_bitstream()
        if self.current_bit_index < len(bitstream):
            transmitted_bit = bitstream[self.current_bit_index]
            observed_bit = self.bus.get_current_bit()

            if self.mode == TRANSMITTING and not self.bus.in_arbitration:
                if message.error_type == "bit_error" and self.current_bit_index == message.error_bit_index:
                    #self.increment_transmit_error()
                    self.bus.broadcast_error_frame("bit_error", self.message_queue[0])
                    self.stop_transmitting()
                    self.current_bit_index = 0
                    return None

            self.current_bit_index += 1
            return transmitted_bit

    def receive_message(self, message):
        if message.identifier not in self.filters:
            print(f"Node {self.node_id} ignored message with ID {message.identifier}.")
        else:
            print(f"Node {self.node_id} received message with ID {message.identifier}.")

        if message.error_type == "stuff_error":
            print(f"Node {self.node_id} detected a Bit Stuffing Error.")
            self.bus.broadcast_error_frame("stuff_error", message)
            return False
        elif message.error_type == "crc_error":
            print(f"Node {self.node_id} detected a CRC Error.")
            self.bus.broadcast_error_frame("crc_error", message)
            return False
        elif message.error_type == "form_error":
            print(f"Node {self.node_id} detected a Form Error.")
            self.bus.broadcast_error_frame("form_error", message)
            return False
        elif message.error_type == "ack_error":
            return False

        # No errors detected; send ACK
        message.update_ack() 
        print(f"Node {self.node_id} sent an ACK bit.")

        return True

    def detect_error_at_bit(self, bit_pos, transmitted_bit, message):
        bitstream = message.get_bitstream()
        
        if self.mode == TRANSMITTING and not self.bus.in_arbitration:
            if transmitted_bit != self.bus.get_current_bit() or transmitted_bit == message.error_bit_index:
                print(f"Node {self.node_id} detected a Bit Monitoring Error.")

    def detect_and_handle_error(self, message):
        if self.error_handler.detect_error(message.error_type, message):
            self.bus.broadcast_error_frame(message.error_type, message)
            return True
        return False

    def handle_overload_frame(self):
        time.sleep(0.1)

    def handle_error_frame(self, error_type):
        if self.state == BUS_OFF:
            return

        if self.mode == TRANSMITTING:
            print(f"Node {self.node_id} detected {error_type} as the transmitter. Incrementing TEC.")
            self.increment_transmit_error()
        elif self.mode == RECEIVING:
            print(f"Node {self.node_id} acknowledged {error_type} error as a receiver.")
            self.increment_receive_error()

    def retransmit_message(self):
        if self.state == BUS_OFF:
            print(f"Node {self.node_id} is in BUS_OFF state and cannot retransmit.")
            self.message_queue.clear()
            return

        if self.has_pending_message():
            self.current_bit_index = 0
            self.mode = TRANSMITTING

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
            self.state = BUS_OFF
            print(f"Node {self.node_id} is in BUS_OFF state.")
        elif self.transmit_error_counter >= 127 or self.receive_error_counter >= 127:
            self.state = ERROR_PASSIVE
            print(f"Node {self.node_id} is in ERROR_PASSIVE state.")
        else:
            self.state = ERROR_ACTIVE

    def has_pending_message(self):
        return len(self.message_queue) > 0

    def reset_node(self):
        self.transmit_error_counter = 0
        self.receive_error_counter = 0
        self.state = ERROR_ACTIVE
        self.mode = WAITING

    def stop_transmitting(self):
        self.mode = WAITING
        self.current_bit_index = 0

    def process_received_bit(self, message, winner_node):
        if self.mode == RECEIVING and self.state != BUS_OFF:
            if message.error_type == "ack_error" and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected an Acknowledgement Error.")
                self.bus.broadcast_error_frame("ack_error", message)
                return False
            elif message.error_type == "stuff_error" and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected a Bit Stuffing Error.")
                self.bus.broadcast_error_frame("stuff_error", message)
                return False
            elif message.error_type == "crc_error" and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected a CRC Error.")
                self.bus.broadcast_error_frame("crc_error", message)
                return False
            elif message.error_type == "form_error" and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected a Form Error.")
                self.bus.broadcast_error_frame("form_error", message)
                return False
            elif message.error_type is None and isinstance(message, (DataFrame, RemoteFrame)) and winner_node.current_bit_index == message.get_ack_index():
                message.update_ack()
        return True
