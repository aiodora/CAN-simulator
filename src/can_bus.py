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
        self.state = IDLE 

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
                self.broadcast_error_frame(message.error_type or "generic_error")
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

        if len(nodes_with_messages) == 1: #only one node tries to transmit
            winner_node = nodes_with_messages[0]
            self.state = BUSY
        else: #more nodes try to send at the same time
            self.in_arbitration = True
            self.state = BUSY
            winner_node = self.perform_arbitration(nodes_with_messages)
            self.in_arbitration = False

        if winner_node:
            self.deliver_message(winner_node)

        for node in self.nodes:
            node.mode = WAITING

    def perform_arbitration(self, nodes_with_messages):
        #nodes_with_messages.sort(key=lambda node: node.message_queue[0][0].identifier)
        #winner_node = nodes_with_messages[0]
        contenders = nodes_with_messages
        bit_pos = 0

        while len(contenders) > 1:
            current_bits = [node.message_queue[0][1][bit_pos] for node in contenders]
            dominant_bit = min(current_bits)
            self.current_bit = dominant_bit
            self.current_bitstream.append(dominant_bit)
            #print(f"Current bit: {dominant_bit}.")
            contenders = [node for node, bit in zip(contenders, current_bits) if bit == dominant_bit]
            bit_pos += 1
        
        winner_node = contenders[0] 
        print(f"Node {winner_node.node_id} won arbitration with ID {winner_node.message_queue[0][0].identifier}.")
        
        for node in nodes_with_messages:
            if node == winner_node:
                node.mode = TRANSMITTING
            else:
                node.mode = RECEIVING
        
        return winner_node

    def deliver_message(self, winner_node):
        if not winner_node.has_pending_message():
            return

        message, bitstream = winner_node.message_queue[0]
        print(f"Node {winner_node.node_id} is delivering message ID {message.identifier}.")
        #print(bitstream)
        print(repr(message))

        ack_received = False
        error_detected = False
        if message.error_type is None:
            self.error = False
        else:
            self.error = True

        for node in self.nodes:
            if node == winner_node:
                continue
            error_detected = node.detect_and_handle_error(message) or error_detected

        if error_detected and message.error_type != "ack_error":
            winner_node.increment_transmit_error()
        else:
            for node in self.nodes:
                if node != winner_node and node.state != BUS_OFF:
                    node.receive_message(message)

        if isinstance(message, RemoteFrame):
            producers = [node for node in self.nodes if message.identifier in node.produced_ids]
            responder = random.choice(producers) if producers else None

            for node in self.nodes:
                if node != winner_node and node.state != BUS_OFF:
                    node.receive_message(message)

                    if message.identifier in node.produced_ids:
                        ack_received = True
                        if node == responder:
                            print(f"Node {node.node_id} responding to Remote Frame with ID {message.identifier}.")
                            response_data = [random.randint(0, 255) for _ in range(8)]
                            node.send_message(message.identifier, response_data, frame_type="data")
                    else:
                        ack_received = True 

            if not producers:
                print(f"No nodes available to respond to Remote Frame with ID {message.identifier}.")

        else:
            for node in self.nodes:
                if node != winner_node and node.state != BUS_OFF:
                    # if node.receive_message(message): 
                    #     continue
                    # else: 
                    #     break

                    if message.error_type == "ack_error":
                        ack_received = False
                    else:
                        ack_received = True

            if not ack_received:
                print(f"Node {winner_node.node_id} detected an ACK Error.")
                winner_node.increment_transmit_error()
                self.broadcast_error_frame("ack_error")
                winner_node.retransmit_message()

            if self.error == False:
                for node in self.nodes: 
                    if node == winner_node:
                        node.decrement_transmit_error()
                    else:
                        node.decrement_receive_error()
                winner_node.message_queue.pop(0)

        for node in self.nodes:
            node.mode = WAITING
        
        self.state = IDLE 

    def get_current_bit(self):
        return self.current_bit
    
    def broadcast_error_frame(self, error_type):
        print(f"Broadcasting error frame for {error_type}.")
        eligible_receivers = [node for node in self.nodes if node.mode == RECEIVING and node.state != BUS_OFF]
        
        if eligible_receivers:
            reporter_node = random.choice(eligible_receivers)
            print(f"Node {reporter_node.node_id} detected the {error_type} error and is reporting it.")
            reporter_node.increment_receive_error()
        # else:
        #     print("No eligible receivers to report the error.")

        for node in self.nodes:
            if node.mode == TRANSMITTING:
                print(f"Node {node.node_id} is the transmitter. Incrementing TEC for {error_type}.")
                node.increment_transmit_error()

        self.reset_nodes_after_error()

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

    def transmit_bit_bit(self, winner_node=None):
        message, bitstream = winner_node.message_queue[0] 
        for bit in bitstream:
            self.current_bit = bit
            self.current_bitstream.append(bit)
            print(f"Node {winner_node.node_id} transmitting bit {bit}.")
            for node in self.nodes:
                if node != winner_node:
                    node.process_received_bit(bitstream.index(bit), bit, message)
            time.sleep(0.1)

        winner_node.message_queue.pop(0)

    def transmit_frame_bit(self, frame):
        bitstream = frame.get_bitstream()
        for bit in bitstream:
            self.current_bit = bit
            self.current_bitstream.append(bit)
            print(f"Transmitting bit: {bit} from standalone frame.")

            for node in self.nodes:
                node.process_received_bit(bit)

            time.sleep(0.1)
