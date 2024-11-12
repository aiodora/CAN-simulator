from can_node import CANNode
from can_message import DataFrame, ErrorFrame, OverloadFrame, RemoteFrame
from can_error_handler import CANErrorHandler
import time

class CANBus:
    def __init__(self):
        self.nodes = []
        self.error_handler = CANErrorHandler()

    def simulate_step(self):
        for node in self.nodes:
            if node.has_pending_message():
                message, _ = node.message_queue[0]

                #print(f"Before checking: {message.frame_type} {message.error_type}")
                if isinstance(message, (ErrorFrame, OverloadFrame)):
                    #print("Detected ErrorFrame or OverloadFrame")
                    self.deliver_message(node)
                    #node.message_queue.pop(0) #discarding the message here
                    return
                #print(f"After checking: {message.frame_type} {message.error_type}")

        competing_nodes = [(node, node.message_queue[0][0]) 
                        for node in self.nodes 
                        if node.has_pending_message() and not isinstance(node.message_queue[0][0], (ErrorFrame, OverloadFrame))]

        if not competing_nodes:
            print("No nodes with pending messages.")
            return
        elif len(competing_nodes) == 1:
            node, message = competing_nodes[0]
            self.deliver_message(node)
            return

        competing_nodes.sort(key=lambda x: x[1].identifier)
        winner_node, winning_message = competing_nodes[0]

        print(f"Node {winner_node.node_id} won arbitration with message ID {winning_message.identifier}")

        self.deliver_message(winner_node)

    def add_node(self, node):
        self.nodes.append(node)
        node.set_bus(self)
        print(f"Node {node.node_id} added to CAN bus.")

    def transmit(self):
        while any(node.has_pending_message() for node in self.nodes):
            competing_nodes = [(node, node.transmit_bit()) for node in self.nodes if node.has_pending_message()]
            if not competing_nodes:
                print("No competing messages.")
                return
            
            winning_bit = min([bit for _, bit in competing_nodes])
            for node, bit in competing_nodes:
                if bit != winning_bit:
                    node.stop_transmitting() 
            
            winner_node = next(node for node, bit in competing_nodes if bit == winning_bit)
            self.deliver_message(winner_node)
            winner_node.message_queue.pop(0)

    def deliver_message(self, winner_node):
        if not winner_node.message_queue:
            return

        message, bitstream = winner_node.message_queue[0]
        print(f"Delivering message with ID {message.identifier} from Node {winner_node.node_id} to all nodes. Error type: {message.error_type}")

        for bit_index, transmitted_bit in enumerate(bitstream):
            bus_bit = transmitted_bit
            for node in self.nodes:
                if node != winner_node:
                    if node.transmit_bit() != transmitted_bit:
                        node.stop_transmitting()

        ack_received = False
        if isinstance(message, DataFrame) or isinstance(message, RemoteFrame):
            for node in self.nodes:
                if node != winner_node:
                    if message.error_type == "bit" and node.error_handler.bit_monitoring(transmitted_bit, bus_bit):
                        #print("Broadcasting bit error frame.")
                        self.broadcast_error_frame("bit_error")
                        return
                    elif message.error_type == "stuff" and node.error_handler.bit_stuffing_check(bitstream):
                        #print("Broadcasting stuffing error frame.")
                        self.broadcast_error_frame("stuff_error")
                        return
                    elif message.error_type == "frame_check" and node.error_handler.frame_check(message):
                        #print("Broadcasting frame check error.")
                        self.broadcast_error_frame("frame_error")
                        return
                    elif message.error_type == "ack" and node.error_handler.acknowledgement_check(message):
                        #print("Broadcasting acknowledgment error frame.")
                        self.broadcast_error_frame("ack_error")
                        return
                    elif message.error_type == "crc" and node.error_handler.crc_check(message, message.calculate_crc()):
                        #print("Broadcasting CRC error frame.")
                        self.broadcast_error_frame("crc_error")
                        return

                    node.receive_message(message)
                    ack_received = True

            if ack_received:
                #print("Message acknowledged by one or more nodes.")
                winner_node.message_queue.pop(0)
            else:
                print("Acknowledgment Error Detected: No node acknowledged the message.")
                self.broadcast_error_frame("ack_error")
                
        elif isinstance(message, ErrorFrame):
            self.broadcast_error_frame("generic error") 
        elif isinstance(message, OverloadFrame):
            #print("Explicit overload frame broadcast.")
            self.broadcast_overload_frame()

    def determine_bus_bit(self, transmitted_bits):
        return 0 if 0 in transmitted_bits else 1 

    def broadcast_error_frame(self, error_type="Error Message"):
        print(f"Error Frame Broadcasting due to {error_type}")
        for node in self.nodes:
            if error_type == "bit_error":
                print("Bit Monitorig Error detected")
            elif error_type == "stuff_error":
                print("Bit Stuffing Error detected")
            elif error_type == "form_error":
                print("Form Error detected")
            elif error_type == "ack_error":
                print("Acknowledgment Error detected")
            elif error_type == "crc_error":
                print("CRC Error detected")
            node.handle_error_frame()

    def broadcast_overload_frame(self):
        print("Overload Frame Broadcasting")
        #overload_frame = OverloadFrame()
        for node in self.nodes:
            node.handle_overload_frame()
        time.sleep(1)
        print("Bus resuming operation.")
