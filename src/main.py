from can_bus import CANBus
from can_node import CANNode
from can_error_handler import CANErrorHandler

def initialize_can_simulation():
    bus = CANBus()
    node1 = CANNode(node_id=1, bus=bus)
    node2 = CANNode(node_id=2, bus=bus)
    bus.add_node(node1)
    bus.add_node(node2)
    return bus, node1, node2

def hardcoded_tests():
    bus, node1, node2 = initialize_can_simulation()
    

if __name__ == "__main__":
    hardcoded_tests()
