from can_message import CANMessage

class PredefinedScenarios:
    def __init__(self, playground, log_panel):
        self.playground = playground
        self.log_panel = log_panel

    def run_message_transmission(self, frame_type):
        self.log_panel.add_log(f"Starting Message Transmission: {frame_type}")
        for node_id, node in self.playground.nodes.items():
            message = CANMessage(
                message_id=node_id * 100,
                data=[node_id, node_id + 1, node_id + 2],
                frame_type=frame_type.lower()
            )
            self.log_panel.add_log(f"Node {node_id} transmitting {frame_type} with ID {message.message_id}")
            self.playground.animate_communication(node_id, message)

    def run_arbitration_test(self):
        self.log_panel.add_log("Starting Arbitration Test")
        message1 = CANMessage(message_id=1, data=[1, 2, 3], frame_type="data")
        message2 = CANMessage(message_id=2, data=[4, 5, 6], frame_type="data")

        self.log_panel.add_log("Node 1 and Node 2 attempting to transmit simultaneously")
        self.playground.animate_communication(1, message1) 
        self.log_panel.add_log("Node 1 wins arbitration")
        self.playground.animate_communication(2, message2) 

    def run_error_injection(self, error_type):
        self.log_panel.add_log(f"Injecting {error_type} Error")
        for node_id, node in self.playground.nodes.items():
            message = CANMessage(
                message_id=node_id * 100,
                data=[node_id, node_id + 1],
                frame_type="data"
            )
            self.playground.animate_communication(node_id, message)
            self.log_panel.add_log(f"Node {node_id} sent a frame. Error {error_type} injected!")

    def run_node_failure_test(self):
        self.log_panel.add_log("Starting Node Failure Test")
        for node_id in range(3, 6):
            node = self.playground.nodes[node_id]
            node.state = "Error Passive"
            self.log_panel.add_log(f"Node {node_id} transitioned to Error Passive state")
            self.playground.update_node_info(node_id, state="Error Passive")
