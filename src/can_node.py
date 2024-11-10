from can_message import DataFrame, ErrorFrame
import random

class CANNode:
    def __init__(self, node_id, message_interval=5000, filters=None, bus=None):
        self.node_id = node_id
        self.bus = bus
        self.message_interval = message_interval
        self.message_queue = [] 
        self.filters = filters if filters else []
        self.state = "Error Active"
        self.transmit_error_counter = 0
        self.receive_error_counter = 0
        self.timer = None 
        self.current_bit_index = 0

    def increment_tec(self): 
        self.transmit_error_counter += 8
        self.check_state_transition()

    def increment_rec(self):
        self.receive_error_counter += 1
        self.check_state_transition()

    def check_state_transition(self):
        if self.transmit_error_counter >= 128 or self.receive_error_counter >= 128: 
            self.state = "Bus Off" 
            self.disconnect_from_bus()
        elif self.transmit_error_counter >= 96 or self.receive_error_counter >= 96:
            self.state = "Error Passive" 
        else:
            self.state = "Error Active"

    def disconnect_from_bus(self):
        self.timer = None 
        self.message_queue.clear()

    def reset_node(self):
        if self.state == "Bus Off":
            self.receive_error_counter = 0
            self.transmit_error_counter = 0
            self.state = "Error Active"

    def set_bus(self, bus):
        self.bus = bus

    def send_message(self, message_id, data=None):
        if self.state == "Bus Off" or self.state == "Error Passive":
            return 

        message = DataFrame(message_id, data)
        message_bitstream = message.get_bitstream()
        self.message_queue.append((message, message_bitstream))
        self.current_bit_index = 0

    def bit_stuffing(self, data):
        stuffed_data = []
        consecutive = 0 
        last_bit = None

        for bit in data: 
            if bit == last_bit:
                consecutive += 1
            else: 
                consecutive = 1

            stuffed_data.append(bit)
            if consecutive == 5: 
                stuffed_data.append(not bit) 
                consecutive = 0

        return stuffed_data
    
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
        consecutive = 0
        last_bit = None

        for bit in data:
            if bit == last_bit:
                consecutive += 1
            else:
                consecutive = 1
                last_bit = bit

            if consecutive > 5: 
                self.increment_tec()
                self.send_error_frame()
                break

    def check_ack_bit(self, message):
        if message.ack_slot == 1:
            self.increment_tec()
            self.send_error_frame()

    def get_next_message(self):
        if self.message_queue:
            return self.message_queue.pop(0)
        return None

    def has_pending_message(self):
        return len(self.message_queue) > 0
    
    def acknowledge_message(self):
        if self.state == "Error Active":
            return random.random() > 0.05
        
        return False

    def receive_message(self, message):
        if not self.is_message_relevant(message.identifier):
            return False 
        
        if message.crc != message.calculate_crc():
            self.increment_rec()
            self.send_error_frame()
            return False
        
        if self.state == "Error Active":
            message.ack_slot = 0
        
        return True

    def is_message_relevant(self, message_id):
        for filter_id in self.filters: 
            if filter_id == message_id:
                return True
            
        return False
    
    def send_error_frame(self):
        if self.bus:
            error_frame = ErrorFrame()
            self.bus.broadcast_error_frame(error_frame)

    def handle_error_frame(self, error_frame):
        self.increment_rec()

    def arbitration_field_length(self):
        return 11
    
    def stop_transmitting(self):
        self.current_bit_index = 0

    def continue_transmitting(self):
        pass

    def reset_transmission_state(self):
        self.current_bit_index = 0
