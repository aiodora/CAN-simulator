class CANBus:
    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)
        node.set_bus(self)
        print(f"Node {node.node_id} added to CAN bus.")

    def transmit(self):
        while any(node.has_pending_message() for node in self.nodes):
            competing_messages = [(node, node.message_queue[0][0]) for node in self.nodes if node.has_pending_message()]

            if not competing_messages:
                print("No new messages.")
                return

            if len(competing_messages) == 1:
                node, message = competing_messages[0]
                self.deliver_message(node)
                node.message_queue.pop(0) 
                continue

            competing_messages.sort(key=lambda x: x[1].identifier)
            winner_node, winning_message = competing_messages[0]

            self.deliver_message(winner_node)
            winner_node.message_queue.pop(0)

    def deliver_message(self, winner_node):
        message, bitstream = winner_node.message_queue[0]
        print(f"Delivering message with ID {message.identifier} to all nodes.")

        for bit_index in range(len(bitstream)): 
            transmitted_bits = [node.transmit_bit() for node in self.nodes]
            bus_bit = self.determine_bus_bit(transmitted_bits)

            for node, transmitted_bit in zip(self.nodes, transmitted_bits):
                node.monitor_bit(transmitted_bit, bus_bit)

        for node in self.nodes:
            node.detect_stuffing_error(message.data_field)

        ack_received = False
        for node in self.nodes:
            if node.is_message_relevant(message.identifier) and node.receive_message(message):
                ack_received = True 

        if ack_received:
            print("Acknowledgement Error Detected: No node acknowledged the message")
            for node in self.nodes:
                node.check_ack_bit(message)

        if message.frame_check():
            print("Form Error: Invalid Frame")
            for node in self.nodes:
                node.send_error_frame()

        for node in self.nodes:
            if node.is_message_relevant(message.identifier):
                node.receive_message(message)

    def determine_bus_bit(self, transmitted_bits):
        return 0 if 0 in transmitted_bits else 1 
    
    def broadcast_error_frame(self, error_frame):
        for node in self.nodes:
            node.handle_error_frame(error_frame)