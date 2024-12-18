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
    def __init__(self, node_id, bus=None, produced_ids=None, filters=None, message_interval=0.025):
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
        self.error_handler = CANErrorHandler()

    def set_bus(self, bus):
        self.bus = bus

    def add_message_to_queue(self, message):
        self.message_queue.append((message, message.get_bitstream()))

    def send_message(self, message_id=None, data=None, frame_type="data", error_type=None, interactive=False):
        if self.state == BUS_OFF:
            print(f"Node {self.node_id} is in BUS_OFF state and cannot transmit.")
            return

        if frame_type == "data":
            message = DataFrame(message_id, self.node_id, data)
        elif frame_type == "remote":
            message = RemoteFrame(message_id, self.node_id)
        elif frame_type == "error":
            message = ErrorFrame(sent_by=self.node_id)
        elif frame_type == "overload":
            message = OverloadFrame(sent_by=self.node_id)
        else:
            print("Invalid frame type specified.")
            return

        if error_type:
            print(f"Injecting {error_type} error into message.")
            self.error_handler.inject_error(error_type, message)
            message.error_type = error_type
        elif interactive and random.random() < 0.1: 
            random_error = random.choice(["bit_error", "stuff_error", "crc_error", "ack_error", "form_error"])
            print(f"Randomly injecting {random_error} error into message.")
            self.error_handler.inject_error(random_error, message)
            message.error_type = error_type

        self.add_message_to_queue(message)
        self.mode = TRANSMITTING 

    def transmit_bit(self):
        if not self.has_pending_message():
            return

        message, bitstream = self.message_queue[0]
        if self.current_bit_index < len(bitstream):
            transmitted_bit = bitstream[self.current_bit_index]
            observed_bit = self.bus.get_current_bit()

            #bit monitoring
            if self.mode == TRANSMITTING and not self.bus.in_arbitration:
                if message.error_type == "bit_error" and self.current_bit_index == message.error_bit_index:
                    print(f"Node {self.node_id} detected a Bit Monitoring Error.")
                    self.increment_transmit_error()
                    self.bus.broadcast_error_frame(message, "bit_monitoring_error")
                    self.stop_transmitting()
                    return None

            self.current_bit_index += 1
            return transmitted_bit

    def receive_message(self, message):
        if message.identifier not in self.filters:
            print(f"Node {self.node_id} ignored message with ID {message.identifier}.")
            #return; doesnt process the message but still can send ack bit
        else:
            print(f"Node {self.node_id} received message with ID {message.identifier}.")

        if message.error_type == "stuff_error":
            print(f"Node {self.node_id} detected a Bit Stuffing Error.")
            self.bus.broadcast_error_frame(message, "stuff_error")
            return False
        elif message.error_type == "crc_error":
            print(f"Node {self.node_id} detected a CRC Error.")
            self.bus.broadcast_error_frame(message, "crc_error")
            return False
        elif message.error_type == "form_error":
            print(f"Node {self.node_id} detected a Form Error.")
            self.bus.broadcast_error_frame(message, "form_error")
            return False
        elif message.error_type == "ack_error":
            return False
        
        message.ack_slot = 0
        print(f"Node {self.node_id} sent an ACK bit.")
        
        return True
    
    def detect_error_at_bit(self, bit_pos, transmitted_bit, message):
        bitstream = message.get_bitstream()
        
        if self.mode == TRANSMITTING and not self.bus.in_arbitration:
            if transmitted_bit != self.bus.get_current_bit():
                print(f"Node {self.node_id} detected a Bit Monitoring Error.")
        
    def detect_and_handle_error(self, message):
        if self.error_handler.detect_error(message.error_type, message):
            #print("here")
            #self.increment_receive_error()
            self.bus.broadcast_error_frame(message, message.error_type)
            return True
        return False

    def handle_overload_frame(self):
        #print(f"Node {self.node_id} detected an Overload Frame. Delaying operations.")
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
            #print(f"Node {self.node_id} retransmitting message ID {self.message_queue[0][0].identifier}.")
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
        # if self.state == BUS_OFF:
            self.transmit_error_counter = 0
            self.receive_error_counter = 0
            self.state = ERROR_ACTIVE
            self.mode = WAITING
            #print(f"Node {self.node_id} reset to ERROR_ACTIVE state.")

    def stop_transmitting(self):
        self.mode = WAITING
        self.current_bit_index = 0

    def process_received_bit(self, message, winner_node):
        if self.mode == RECEIVING and self.state != BUS_OFF:
            #print(f"Node {self.node_id} received bit: {bit}")
            if message.error_type == "ack_error" and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected an Acknowledgement Error.")
                self.bus.broadcast_error_frame(message, "stuff_error")
                #print(f"Node {self.node_id} detected a bit error.")
                return False
            elif message.error_type == "stuff_error"  and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected a Bit Stuffing Error.")
                self.bus.broadcast_error_frame(message, "stuff_error")
                return False
            elif message.error_type == "crc_error" and winner_node.current_bit_index == message.error_bit_index:
                print(f"Node {self.node_id} detected a CRC Error.")
                self.bus.broadcast_error_frame(message, "crc_error")
                return False
            elif message.error_type == "form_error" and winner_node.current_bit_index == message.error_bit:
                print(f"Node {self.node_id} detected a Form Error.")
                self.bus.broadcast_error_frame(message, "form_error")
                return False
            elif message.error_type == None and (message.isinstance(DataFrame) or message.isinstance(RemoteFrame)) and winner_node.current_bit_index == message.get_ack_index():
                message.ack_slot = 0 
        return True