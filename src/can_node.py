from can_message import DataFrame, ErrorFrame, RemoteFrame, OverloadFrame
from can_error_handler import CANErrorHandler
import random
import time

TRANSMITTING = "transmitting"
RECEIVING = "receiving"
WAITING ="waiting"

class CANNode:
    def __init__(self, node_id, message_interval=5000, produced_ids=None, filters=None, bus=None):
        self.node_id = node_id
        self.bus = bus
        self.message_interval = message_interval
        self.message_queue = [] 
        self.produced_ids = produced_ids if produced_ids else list(range(0, 2047))
        self.filters = filters if filters else list(range(0, 2047))
        self.state = "Error Active"
        self.transmit_error_counter = 0
        self.receive_error_counter = 0
        self.error_handler = CANErrorHandler()
        self.current_bit_index = 0
        self.state = WAITING

    def set_bus(self, bus):
        self.bus = bus

    def increment_tec(self): 
        self.transmit_error_counter += 8
        self.check_state_transition()

    def increment_rec(self):
        self.receive_error_counter += 1
        self.check_state_transition()

    def decrement_counters(self):
        if self.transmit_error_counter > 0:
            self.transmit_error_counter -= 1 
        if self.receive_error_counter > 0: 
            self.receive_error_counter -= 1 

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

    def send_message(self, message_id=None, data=None, frame_type="data", error_type=None):
        if self.state == "Bus Off" or self.state == "Error Passive":
            return
        
        if frame_type == "data":
            message = DataFrame(message_id, data)
        elif frame_type == "remote":
            message = RemoteFrame(message_id)
        elif frame_type == "error":
            message = ErrorFrame()
        elif frame_type == "overload":
            message = OverloadFrame()
        else:
            print("Invalid frame type specified.")
            return
        
        if error_type:
            print(f"Injecting {error_type} error into message.")
            self.error_handler.inject_error(error_type, message)
            message.error_type = error_type
        
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
        self.state = RECEIVING
        if self.error_handler.bit_stuffing_check(message.get_bitstream()):
            print(f"Node {self.node_id} detected Bit Stuffing Error.")
            self.increment_rec() 
            self.state = WAITING
            return False
        
        unstuffed_bitstream = self.unstuff_bits(message.get_bitstream())

        if not self.error_handler.frame_check(message):
            print(f"Node {self.node_id} detected Frame Check Error.")
            self.increment_rec()
            self.state = WAITING
            return False 
        
        if self.state == "Error Active":
            message.ack_slot = 0
            if self.error_handler.acknowledgement_check(message):
                print(f"Node {self.node_id} detected Acknowledgment Error.")
                self.increment_tec() 
                self.state = WAITING
                return False
            
        calculated_crc = message.calculate_crc()
        if self.error_handler.crc_check(message, calculated_crc):
            print(f"Node {self.node_id} detected CRC Error.")
            self.increment_rec()
            self.state = WAITING
            return False 
        
        if self.state == "Error Active":
            message.ack_slot = 0 

        if isinstance(message, DataFrame):
            if message.identifier in self.filters:
                print(f"Node {self.node_id} received and processed message with ID {message.identifier}")
            else: 
                print(f"Node {self.node_id} received message with ID {message.identifier}")
        elif isinstance(message, RemoteFrame):
            if message.identifier in self.produced_ids: 
                print(f"Node {self.node_id} received Remote Frame with ID {message.identifier} and is responding.")
                response_data = [random.randint(0, 255) for _ in range(8)]
                self.send_message(message.identifier, response_data, frame_type="data")
            else: 
                print(f"Node {self.node_id} received Remote Frame with ID {message.identifier} but is not the producer.")

        self.decrement_counters()
        self.state = WAITING
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
        error_frame = ErrorFrame()
        self.bus.broadcast_error_frame(error_frame)

    def discard_message(self):
        if self.message_queue:
            self.message_queue.pop(0)

    def handle_error_frame(self):
        print(f"Node {self.node_id} detected Error Frame; discarding current message.")
        self.discard_message()
        self.increment_rec()

    def handle_overload_frame(self):
        print(f"Node {self.node_id} detected Overload Frame; transmission delayed temporarily.")
        self.discard_message()
        #time.sleep(0.1)

    def has_pending_message(self):
        return len(self.message_queue) > 0

    def is_message_relevant(self, message_id):
        return message_id in self.filters

    def arbitration_field_length(self):
        return 11

    def stop_transmitting(self):
        self.current_bit_index = 0
