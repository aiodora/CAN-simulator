class CANBus:
    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)
        node.set_bus(self)
        print(f"Node {node.node_id} added to CAN bus.")

    def transmit(self):
        while any(node.has_pending_message() for node in self.nodes):
            competing_messages = [(node, node.message_queue[0]) for node in self.nodes if node.has_pending_message()]

            if not competing_messages:
                print("No new messages.")
                return

            if len(competing_messages) == 1:
                node, message = competing_messages[0]
                self.deliver_message(message)
                node.message_queue.pop(0) 
                continue

            print("\n--- Starting Arbitration Process ---")

            competing_messages.sort(key=lambda x: x[1].identifier)
            winner_node, winning_message = competing_messages[0]

            print(f"\nArbitration Winner: Node {winner_node.node_id} with Message ID {winning_message.identifier}")
            self.deliver_message(winning_message)
            winner_node.message_queue.pop(0) 

    def deliver_message(self, message):
        print(f"Delivering message with ID {message.identifier} to all nodes.")
        for node in self.nodes:
            node.receive_message(message)
