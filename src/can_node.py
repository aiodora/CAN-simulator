from can_message import DataFrame

class CANNode:
    def __init__(self, node_id, bus=None):
        self.node_id = node_id
        self.bus = bus
        self.message_queue = [] 
        self.state = "Error Active"
        self.transmit_error_counter = 0
        self.receive_error_counter = 0

    def increment_tec(self): 
        self.transmit_error_counter += 8
        self.check_state_transition()

    def check_state_transition(self):
        if self.transmit_error_counter >= 128 or self.receive_error_counter >= 128: 
            self.state = "Bus Off"
        elif self.transmit_error_counter >= 96 or self.receive_error_counter >= 96:
            self.state = "Error Passive"
        else:
            self.state = "Error Active"

    def set_bus(self, bus):
        self.bus = bus

    def send_message(self, message_id, data=None):
        message = DataFrame(message_id, data)
        self.message_queue.append(message)
        print(f"Node {self.node_id} queued message with ID {message_id}")

    def get_next_message(self):
        if self.message_queue:
            return self.message_queue.pop(0)
        return None

    def has_pending_message(self):
        return len(self.message_queue) > 0

    def receive_message(self, message):
        print(f"Node {self.node_id} received message: ID={message.identifier}, Data={message.data_field}")
