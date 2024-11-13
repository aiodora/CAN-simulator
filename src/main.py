import time
from can_bus import CANBus
from can_node import CANNode
from can_message import DataFrame, RemoteFrame, ErrorFrame, OverloadFrame

def initialize_can_simulation():
    bus = CANBus()
    node1 = CANNode(node_id=1, bus=bus)
    node2 = CANNode(node_id=2, produced_ids=[], bus=bus)
    node3 = CANNode(node_id=3, filters=[200], bus=bus)
    bus.add_node(node1)
    bus.add_node(node2)
    bus.add_node(node3)
    return bus, node1, node2, node3 

def run_tests():
    bus, node1, node2, node3 = initialize_can_simulation()

    print("\nTransmission and Arbitration Tests")

    print("\nI. Single-Node Transmission")
    node1.send_message(500, [1, 2, 3, 4])
    bus.simulate_step() 

    print("\nII. Multi-Node Arbitration")
    node1.send_message(200, [10, 20, 30, 40]) 
    node2.send_message(100, [5, 15, 25, 35]) 
    bus.simulate_step() 
    bus.simulate_step()

    print("\nIII. Sequential Transmission")
    node1.send_message(300, [6, 7, 8])
    node1.send_message(400, [9, 10, 11])
    bus.simulate_step() 
    bus.simulate_step()

    print("\nNo new messages added:")
    bus.simulate_step()

    print("\nIV. Remote Frame Transmission")
    node1.send_message(710, None, "remote")
    bus.simulate_step()
    bus.simulate_step()

    print("\nV. Error Frame Transmission")
    node2.send_message(None, None, "error")
    bus.simulate_step()

    print("\nVI. Overload Frame Transmission")
    node3.send_message(None, None, "overload")
    bus.simulate_step()

    #test_all_errors(bus, node1)

def test_all_errors(bus, node):
    print("\nTesting Error Detection Mechanisms")

    #need to keep working on the first 2 
    # print("\n\t Bit Monitoring Error")
    # node.send_message(800, [1, 1, 1, 1], error_type="bit")
    # bus.simulate_step()

    # print("\n\t Bit Stuffing Error")
    # node.send_message(101, [0x1F, 0x1F, 0x1F], error_type="stuff")
    # bus.simulate_step()

    # print("\n\t Frame Check Error")
    # node.send_message(102, [2, 2, 2, 2], error_type="frame_check")
    # node.increment_tec()
    # bus.simulate_step()

    # print("\n\t Acknowledgment Error")
    # node.send_message(103, [3, 3, 3, 3], error_type="ack")
    # bus.simulate_step()

    # print("\n\t CRC Check Error")
    # node.send_message(104, [4, 4, 4, 4], frame_type="data", error_type="crc")
    # bus.simulate_step()

if __name__ == "__main__":
    run_tests()

