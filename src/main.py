# main.py
import time
from can_bus import CANBus
from can_node import CANNode, ERROR_ACTIVE
from can_message import DataFrame, RemoteFrame, ErrorFrame, OverloadFrame

def setup_can_network():
    """
    Creates a CANBus and three CANNodes, connects them, and returns them.
    """
    bus = CANBus()
    node1 = CANNode(node_id=1)
    node2 = CANNode(node_id=2)
    node3 = CANNode(node_id=3)

    bus.connect_node(node1)
    bus.connect_node(node2)
    bus.connect_node(node3)

    return bus, node1, node2, node3

def test_bit_error_detection():
    """
    Example test: Node1 sends a message with a forced 'bit_error',
    and we verify the resulting TEC/REC increments.
    """
    print("\n=== TEST: bit_error_detection ===")
    bus, node1, node2, node3 = setup_can_network()

    # Node1 sends with a 'bit_error'
    node1.send_message(message_id=101, data=[0x01, 0x02], error_type="bit_error")

    # Step the bus a few times to see the error detection
    for _ in range(100):
        bus.simulate_step()

    # Print out error counters for debugging
    print(f"Node1 => REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node2 => REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node3 => REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

def test_crc_error_detection():
    """
    Node1 sends a message with 'crc_error' injection.
    We expect Node1's TEC to increment and other nodes' REC to increment.
    """
    print("\n=== TEST: crc_error_detection ===")
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=23, data=[0x01, 0x02, 0x03], error_type="crc_error")
    print(f"Correct CRC: {node1.message_queue[0].calculate_crc()}")
    print(f"After CRC error injection: {node1.message_queue[0].crc}")

    # Step the bus multiple times for bit-by-bit detection
    for _ in range(100):
        bus.simulate_step()

    print(f"Node1 => REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node2 => REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node3 => REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

def test_ack_error_detection():
    """
    Node1 sends a message with 'ack_error', so it should never receive an ACK,
    resulting in a transmit error increment for Node1.
    """
    print("\n=== TEST: ack_error_detection ===")
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=103, data=[0x01, 0x02], error_type="ack_error")

    # Step the bus multiple times
    for _ in range(100):
        bus.simulate_step()

    print(f"Node1 => REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node2 => REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node3 => REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

def test_state_transitions():
    """
    Keep sending error frames from Node1 until it goes to ERROR_PASSIVE, then BUS_OFF.
    """
    print("\n=== TEST: state_transitions ===")
    bus, node1, node2, node3 = setup_can_network()

    # 16 transmissions with form_error => each increments node1's TEC by 8 => 128 => ERROR_PASSIVE
    print("Forcing Node1 to transition to ERROR_PASSIVE...")
    msg_id = 101
    node1.transmit_error_counter = 126
    for _ in range(70):
        node1.send_message(message_id=msg_id, data=[0x01, 0x02], error_type="form_error")
        bus.simulate_step()
        msg_id += 1
    print(f"Node1 => state={node1.state}, REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")

    print(f"Node1 final state: {node1.state}")

    node1.transmit_error_counter = 253
    # Additional transmissions to push Node1 to BUS_OFF
    print("Forcing Node1 to transition to BUS_OFF...")
    for _ in range(65):
        node1.send_message(message_id=msg_id, data=[0x01, 0x02], error_type="form_error")
        bus.simulate_step()
        msg_id += 1
        print(f"Node1 => state={node1.state}, REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")

def test_retransmissions():
    """
    Node1 sends a message with bit_error. We expect Node1 to keep the message 
    in the queue and attempt retransmission next time if an error is detected.
    """
    print("\n=== TEST: retransmissions ===")
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=106, data=[0x01, 0x02], error_type="bit_error")

    for _ in range(5):
        bus.simulate_step()

    # If the message is still there => hasn't been fully transmitted or was retransmitted
    if node1.has_pending_message():
        print("Retransmission Test Passed (Message is still pending).")
    else:
        print("Retransmission might have been lost or handled differently. Check logic.")

def test_simple_frame_transmission():
    """
    Just send a normal DataFrame, a RemoteFrame, an ErrorFrame, and OverloadFrame.
    """
    print("\n=== TEST: simple_frame_transmission ===")
    bus, node1, node2, node3 = setup_can_network()

    # DataFrame
    node1.send_message(message_id=200, data=[0xAA, 0xBB])
    for _ in range(70):
        bus.simulate_step()

    # RemoteFrame
    # node2.send_message(message_id=201, frame_type="remote")
    # for _ in range(5):
    #     bus.simulate_step()

    # # ErrorFrame
    # node3.send_message(frame_type="error")
    # for _ in range(5):
    #     bus.simulate_step()

    # # OverloadFrame
    # node1.send_message(frame_type="overload")
    # for _ in range(5):
    #     bus.simulate_step()

    print("Simple Frame Transmission Test finished.")

def test_arbitration():
    """
    Node1, Node2, Node3 each send a DataFrame with different ID. 
    The node with the lowest ID should eventually win arbitration bit-by-bit.
    """
    print("\n=== TEST: arbitration ===")
    bus, node1, node2, node3 = setup_can_network()

    # Node1 => ID=101
    node1.send_message(message_id=101, data=[0x01, 0x02])
    # Node2 => ID=100 (lowest => should eventually win)
    node2.send_message(message_id=100, data=[])
    # Node3 => ID=102
    node3.send_message(message_id=102, data=[0x05, 0x06])
    print(f"Message from node 1 id in binary: {node1.message_queue[0].identifier :011b}") 
    print(f"Message from node 2 id in binary: {node2.message_queue[0].identifier :011b}")
    print(f"Message from node 3 id in binary: {node3.message_queue[0].identifier :011b}")

    # Step bus multiple times to see the arbitration
    for _ in range(100):
        bus.simulate_step()

    print("Arbitration Test finished.")

def test_stuffing_and_form_errors():
    """
    Node1 sends a 'stuff_error'; Node2 sends a 'form_error'. We watch counters.
    """
    print("\n=== TEST: stuffing_and_form_errors ===")
    bus, node1, node2, node3 = setup_can_network()

    print("1) Testing Stuffing Error from Node1")
    node1.send_message(message_id=101, data=[0x01, 0x02], frame_type="data", error_type="stuff_error")
    for _ in range(5):
        bus.simulate_step()
    print(f"Node1 => REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node2 => REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node3 => REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

    print("2) Node2 sends a correct message to decrement counters")
    node2.send_message(message_id=99, data=[0x01, 0x02], frame_type="data", error_type=None)
    for _ in range(5):
        bus.simulate_step()

    print("3) Testing Form Error from Node2")
    node2.send_message(message_id=101, data=[0x03, 0x00], frame_type="data", error_type="form_error")
    for _ in range(5):
        bus.simulate_step()

    print("4) Another correct message from Node2 to decrement counters")
    node2.send_message(message_id=103, data=[0x01, 0x02], frame_type="data", error_type=None)
    for _ in range(5):
        bus.simulate_step()

if __name__ == "__main__":
    print("Starting CAN Simulation Tests...\n")

    # Uncomment whichever tests you want to run:

    # test_simple_frame_transmission()
    # test_sequential_transmission()  # if you create one
    #test_bit_error_detection()
    #test_crc_error_detection()
    #test_ack_error_detection()
    test_state_transitions()
    # test_retransmissions()
    #test_arbitration()
    # test_stuffing_and_form_errors()

    #print("\nAll requested tests complete.")
