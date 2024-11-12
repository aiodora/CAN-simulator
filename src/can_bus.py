from can_node import CANNode
from can_message import DataFrame, ErrorFrame
from can_error_handler import CANErrorHandler

class CANBus:
    def __init__(self):
        self.nodes = []
        self.error_handler = CANErrorHandler()

    def simulate_step(self):
        competing_nodes = [(node, node.message_queue[0][0]) for node in self.nodes if node.has_pending_message()]

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

    def deliver_message(self, winner_node, error_type=None):
        if not winner_node.message_queue:
            return

        message, bitstream = winner_node.message_queue[0]
        print(f"Delivering message with ID {message.identifier} from Node {winner_node.node_id} to all nodes.")

        arbitration_phase = True

        for bit_index in range(len(bitstream)):
            transmitted_bit = bitstream[bit_index]
            bus_bit = transmitted_bit 

            for node in self.nodes:
                if node != winner_node:
                    if arbitration_phase:
                        if node.transmit_bit() != transmitted_bit:
                            node.stop_transmitting() 

            if bit_index >= len(f"{message.identifier:011b}") - 1:
                arbitration_phase = False

            bus_bit = min(transmitted_bit, bus_bit)
        ack_received = True
        for node in self.nodes:
            if node != winner_node:
                node.receive_message(message) 

        winner_node.message_queue.pop(0)

    def determine_bus_bit(self, transmitted_bits):
        return 0 if 0 in transmitted_bits else 1 

    def broadcast_error_frame(self, error_frame):
        for node in self.nodes:
            node.handle_error_frame()
