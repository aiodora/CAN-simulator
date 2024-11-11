from can_message import DataFrame, ErrorFrame
from can_error_handler import CANErrorHandler
import random

class CANNode:
    def __init__(self, node_id, message_interval=5000, filters=None, bus=None):
        self.node_id = node_id
        self.bus = bus
        self.message_interval = message_interval
        self.message_queue = [] 
        self.filters = filters if filters else list(range(0, 2048))
        self.state = "Error Active"
        self.transmit_error_counter = 0
        self.receive_error_counter = 0
        self.error_handler = CANErrorHandler()
        self.current_bit_index = 0 

    def set_bus(self, bus):
        self.bus = bus

    def increment_tec(self): 
        self.transmit_error_counter += 8
        self.check_state_transition()

    def increment_rec(self):
        self.receive_error_counter += 1
        self.check_state_transition()

    def check_state_transition(self):
        if self.transmit_error_counter >= 255 or self.receive_error_counter >= 255:
            self.state = "Bus Off"
            self.disconnect_from_bus()
        elif self.transmit_error_counter >= 127 or self.receive_error_counter >= 127:
            self.state = "Error Passive"
        else:
            self.state = "Error Active"

    def disconnect_from_bus(self):
        self.message_queue.clear()

    def reset_node(self):
        if self.state == "Bus Off":
            self.transmit_error_counter = 0
            self.receive_error_counter = 0
            self.state = "Error Active"

    def send_message(self, message_id, data=None):
        if self.state == "Bus Off" or self.state == "Error Passive":
            return
        message = DataFrame(message_id, data)
        message_bitstream = message.get_bitstream()
        self.message_queue.append((message, message_bitstream))
        self.current_bit_index = 0

    def retransmit(self):
        if self.state == "Error Passive" or self.state == "Bus Off":
            return
        if self.has_pending_message():
            message, bitstream = self.message_queue[0]
            print(f"Retransmitting message with ID {message.identifier} from node {self.node_id}")
            self.send_message(message.identifier, message.data_field)
            self.bus.simulate_step()

    def transmit_bit(self):
        if self.has_pending_message():
            message, bitstream = self.message_queue[0]
            if self.current_bit_index < len(bitstream):
                bit = bitstream[self.current_bit_index]
                self.current_bit_index += 1
                return bit
            else:
                self.current_bit_index = 0 
                return 1 
        return 1

    def monitor_bit(self, transmitted_bit, bus_bit):
        if transmitted_bit != bus_bit:
            if self.current_bit_index <= self.arbitration_field_length():
                self.stop_transmitting() 
            elif self.state == "Error Active":
                self.increment_tec()
                self.send_error_frame()

    def detect_stuffing_error(self, data):
        if self.error_handler.bit_stuffing_check(data):
            self.increment_tec()
            self.send_error_frame()

    def check_ack_bit(self, message):
        if self.error_handler.acknowledgement_check(message):
            self.increment_tec()
            self.send_error_frame()

    def receive_message(self, message):
        if not self.is_message_relevant(message.identifier):
            return False
        if self.error_handler.crc_check(message, message.calculate_crc()):
            self.increment_rec()
            self.send_error_frame()
            return False
        if self.state == "Error Active":
            message.ack_slot = 0 
        return True
    
    def unstuff_bits(self, bitstream):
        unstuffed_bits = []
        consecutive_count = 0
        last_bit = None
        for bit in bitstream:
            if bit == last_bit:
                consecutive_count += 1
                if consecutive_count == 5:
                    continue 
            else:
                consecutive_count = 1
            unstuffed_bits.append(bit)
            last_bit = bit
        return unstuffed_bits

    def send_error_frame(self):
        if self.bus:
            error_frame = ErrorFrame()
            self.bus.broadcast_error_frame(error_frame)

    def handle_error_frame(self, error_frame):
        self.increment_rec()

    def has_pending_message(self):
        return len(self.message_queue) > 0

    def is_message_relevant(self, message_id):
        return message_id in self.filters

    def arbitration_field_length(self):
        return 11

    def stop_transmitting(self):
        self.current_bit_index = 0