import time
from can_bus import CANBus
from can_node import CANNode
from can_message import DataFrame, RemoteFrame, ErrorFrame, OverloadFrame

def initialize_can_simulation():
    bus = CANBus()
    node1 = CANNode(node_id=1, bus=bus)
    node2 = CANNode(node_id=2, bus=bus)
    node3 = CANNode(node_id=3, filters=[200], bus=bus)
    bus.add_node(node1)
    bus.add_node(node2)
    bus.add_node(node3)
    return bus, node1, node2, node3 

def test_frame_with_errors(bus, node, frame_type, error_type=None):
    if frame_type == "data":
        print("\n--- Testing Data Frame ---")
        message = DataFrame(700, [10, 20, 30, 40])
    elif frame_type == "remote":
        print("\n--- Testing Remote Frame ---")
        message = RemoteFrame(701)
    elif frame_type == "error":
        print("\n--- Testing Error Frame ---")
        message = ErrorFrame()
    elif frame_type == "overload":
        print("\n--- Testing Overload Frame ---")
        message = OverloadFrame()
    else:
        print(f"Invalid frame type: {frame_type}")
        return

    if error_type:
        print(f"Injecting {error_type} error into {frame_type} frame")

        if error_type == "frame_check":
            message.crc_delimiter = 0 
            message.ack_delimiter = 0 
            message.end_of_frame = [0] * 7 
            message.intermission = [0] * 3 
        elif error_type == "crc":
            message.crc = 0xFFFF 
        elif error_type == "bit":
            original_bitstream = message.get_bitstream()
            modified_bitstream = [1 - bit if i == 0 else bit for i, bit in enumerate(original_bitstream)]
            message.get_bitstream = lambda: modified_bitstream 
        elif error_type == "stuff":
            stuffed_bitstream = message.get_bitstream() + [0] * 6
            message.get_bitstream = lambda: stuffed_bitstream
        elif error_type == "ack":
            message.ack_slot = 1 

    node.message_queue.append((message, message.get_bitstream()))

    bus.simulate_step()

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

if __name__ == "__main__":
    run_tests()
