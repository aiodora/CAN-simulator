from can_node import CANNode, WAITING, TRANSMITTING, RECEIVING, BUS_OFF 
from can_message import DataFrame, ErrorFrame, OverloadFrame, RemoteFrame
import random 
import time

IDLE = "Idle"
BUSY = "Busy"

class CANBus:
    def __init__(self):
        self.nodes = []  
        self.current_bit = 1 #by default the current bit that is sent is 1 
        self.in_arbitration = False  
        self.error = False
        self.current_bitstream = [] 
        self.bitstream_display = [] #using this for the simulation 
        self.state = IDLE 
        self.error_reported = False

    def connect_node(self, node):
        self.nodes.append(node)
        node.set_bus(self)
        print(f"Node {node.node_id} connected to the bus.")

    def simulate_step(self):
        nodes_with_messages = [node for node in self.nodes if node.has_pending_message()]

        if not nodes_with_messages:
            print("No nodes with pending messages.")
            self.state = IDLE 
            self.current_bitstream.append(1)
            return

        for node in nodes_with_messages:
            message, _ = node.message_queue[0]
            if isinstance(message, ErrorFrame):
                print(f"Node {node.node_id} broadcasting an Error Frame.")
                self.state = BUSY
                self.broadcast_error_frame(None, message.error_type or "generic_error")
                node.message_queue.pop(0) 
                node.mode = WAITING
                return
            elif isinstance(message, OverloadFrame):
                print(f"Node {node.node_id} broadcasting an Overload Frame.")
                self.state = BUSY
                self.broadcast_overload_frame()
                node.message_queue.pop(0) 
                node.mode = WAITING
                return
            
        for node in self.nodes: 
            node.mode = RECEIVING

        for node in nodes_with_messages:
            node.mode = TRANSMITTING

        self.current_bitstream.clear()
        self.bitstream_display.clear()

        from_bit = 0
        if len(nodes_with_messages) == 1: #only one node tries to transmit
            winner_node = nodes_with_messages[0]
            self.state = BUSY
        else: #more nodes try to send at the same time
            self.in_arbitration = True
            self.state = BUSY
            winner_node, from_bit = self.perform_arbitration(nodes_with_messages)
            self.in_arbitration = False

        if winner_node:
            self.deliver_message(winner_node, from_bit)

        for node in self.nodes:
            node.mode = WAITING

    def perform_arbitration(self, nodes_with_messages):
        #nodes_with_messages.sort(key=lambda node: node.message_queue[0][0].identifier)
        #winner_node = nodes_with_messages[0]
        contenders = nodes_with_messages
        bit_pos = 0

        while len(contenders) > 1 and bit_pos < 12:
            current_bits = [node.message_queue[0][1][bit_pos] for node in contenders]
            dominant_bit = min(current_bits)
            self.current_bit = dominant_bit
            self.current_bitstream.append(dominant_bit)
            self.bitstream_display.append(dominant_bit)
            print(f"Bit {bit_pos}: {dominant_bit}.")
            contenders = [node for node, bit in zip(contenders, current_bits) if bit == dominant_bit]
            for node in self.nodes:
                if (node not in contenders) and (node.mode == TRANSMITTING):
                    node.mode = RECEIVING
                    print(f"Node {node.node_id} is in RECEIVING mode.")
                elif (node in contenders): 
                    node.mode = TRANSMITTING
            bit_pos += 1
        
        winner_node = contenders[0] 
        print(f"Node {winner_node.node_id} won arbitration with ID {winner_node.message_queue[0][0].identifier}.")
        
        return winner_node, bit_pos

    def deliver_message(self, winner_node, from_bit):
        if not winner_node.has_pending_message():
            return

        message, bitstream = winner_node.message_queue[0]

        def flatten_bitstream(bitstream):
            flat_bits = []
            for segment in bitstream:
                if isinstance(segment, list):
                    flat_bits.extend(segment) 
                else:
                    flat_bits.append(segment) 
            return flat_bits

        flattened_bits = flatten_bitstream(bitstream)
        print(f"Node {winner_node.node_id} is delivering message ID {message.identifier}.")
        #print(bitstream)
        #print(flattened_bits)
        print(repr(message))

        self.error_reported = False 

        self.current_bitstream = []

        for node in self.nodes:
            if node == winner_node:
                continue
            if not self.error_reported and node.detect_and_handle_error(message):
                self.error_reported = True 
                self.broadcast_error_frame(message.error_type, message)
                break

        if not self.error_reported:
            for node in self.nodes:
                if node != winner_node and node.state != BUS_OFF:
                    node.receive_message(message)

            for node in self.nodes:
                if node.mode == RECEIVING and node.state != BUS_OFF:
                    node.decrement_receive_error()
                elif node.mode == TRANSMITTING:
                    node.decrement_transmit_error()

            print(repr(message))
            print(flatten_bitstream(message.get_bitstream()))
            winner_node.message_queue.pop(0)

        for node in self.nodes:
            node.mode = WAITING
        
        self.state = IDLE 

    def get_current_bit(self):
        return self.current_bit
    
    def broadcast_error_frame(self, message, error_type):
        if self.error_reported:
            return 
        
        eligible_receivers = [node for node in self.nodes if node.mode == RECEIVING and node.state != BUS_OFF]
        self.current_bitstream.clear()
        self.bitstream_display.clear()

        error_frame_printed = False 
        
        if eligible_receivers:
            reporter_node = random.choice(eligible_receivers)
            if message != None:
                print(f"Node {reporter_node.node_id} detected the {error_type} error in the message {message.identifier} and is reporting it.")
                print(f"Broadcasting error frame for {error_type}.")
            else: 
                print(f"Node {reporter_node.node_id} detected a generic error and is reporting it.")
                print(f"Broadcasting error frame.")
            #reporter_node.increment_receive_error()
        # else:
        #     print("No eligible receivers to report the error.")

        for node in self.nodes:
            if node.mode == RECEIVING and node.state != BUS_OFF:
                node.increment_receive_error()
            elif node.mode == TRANSMITTING:
                node.increment_transmit_error()

        self.error_reported = True
        self.reset_nodes_after_error()
        self.transmit_frame_bit(ErrorFrame(sent_by=None))

    def reset_nodes_after_error(self):
        for node in self.nodes:
            node.mode = WAITING
        self.state = IDLE

    def broadcast_overload_frame(self):
        print("Broadcasting overload frame.")
        overload_frame = OverloadFrame(sent_by=None)
        self.transmit_frame_bit(overload_frame)
        for node in self.nodes:
            node.handle_overload_frame()
        print("Overload frame processing complete.")

    def transmit_bit_by_bit(self, winner_node):
        if not winner_node.has_pending_message():
            return

        message, bitstream = winner_node.message_queue[0]
        print(f"Node {winner_node.node_id} starts transmitting Message ID {message.identifier}.")

        def send_bit_step(bit_index):
            if bit_index < len(bitstream):
                transmitted_bit = bitstream[bit_index]
                self.current_bit = transmitted_bit
                self.current_bitstream.append(transmitted_bit)

                for node in self.nodes:
                    if node != winner_node:
                        node.process_received_bit(message, winner_node)

                if message.error_type == "bit_error" and bit_index == message.error_bit_index:
                    print(f"Node {winner_node.node_id} detected a Bit Monitoring Error at Bit {bit_index}")
                    self.broadcast_error_frame(message, "bit_error")
                    return 

                time.sleep(0.1)  
                send_bit_step(bit_index + 1)
            else:
                print(f"Node {winner_node.node_id} successfully transmitted Message ID {message.identifier}.")
                winner_node.current_bit_index = 0
                winner_node.message_queue.pop(0)
                self.state = IDLE
                for node in self.nodes:
                    node.mode = WAITING

        send_bit_step(0)

    def transmit_frame_bit(self, frame):
        self.current_bitstream.clear()
        bitstream = frame.get_bitstream()
        for bit in bitstream:
            self.current_bit = bit
            self.current_bitstream.append(bit)

            for node in self.nodes:
                node.process_received_bit(bit, None)

            time.sleep(0.1)
        print(f"End of {frame}.")