import time
from can_bus import CANBus
from can_node import CANNode, ERROR_ACTIVE
from can_message import DataFrame, RemoteFrame, ErrorFrame, OverloadFrame

def setup_can_network():
    bus = CANBus()
    node1 = CANNode(node_id=1)
    node2 = CANNode(node_id=2)
    node3 = CANNode(node_id=3)
    
    bus.connect_node(node1)
    bus.connect_node(node2)
    bus.connect_node(node3)
    
    return bus, node1, node2, node3

def test_bit_error_detection():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=101, data=[0x01, 0x02], error_type="bit_error")
    bus.simulate_step()

    assert node1.transmit_error_counter == 8, "TEC not incremented correctly for bit error."
    print(f"Node 1 TEC after bit error: {node1.transmit_error_counter}")

    assert node2.receive_error_counter == 1, "REC not incremented correctly for node 2."
    assert node3.receive_error_counter == 1, "REC not incremented correctly for node 3."
    print(f"Node 2 REC: {node2.receive_error_counter}")
    print(f"Node 3 REC: {node3.receive_error_counter}")

def test_crc_error_detection():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=102, data=[0x01, 0x02, 0x03], error_type="crc_error")
    bus.simulate_step()

    assert node1.transmit_error_counter == 8, "TEC not incremented correctly for CRC error."
    print(f"Node 1 TEC after CRC error: {node1.transmit_error_counter}")

    assert node2.receive_error_counter == 1, "REC not incremented correctly for node 2."
    assert node3.receive_error_counter == 1, "REC not incremented correctly for node 3."
    print(f"Node 2 REC: {node2.receive_error_counter}")
    print(f"Node 3 REC: {node3.receive_error_counter}")

def test_ack_error_detection():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=103, data=[0x01, 0x02], error_type="ack_error")
    bus.simulate_step()
  
    assert node1.transmit_error_counter == 8, "TEC not incremented correctly for ACK error."
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

def test_state_transitions():
    bus, node1, node2, node3 = setup_can_network()
    msg_id = 101; 
    for _ in range(16):  #16 * 8 = 128 > 127 -> node should go in Error Passive at the end of this for
        node1.send_message(message_id=msg_id, data=[0x01, 0x02], error_type="form_error")
        bus.simulate_step()
        print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
        print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
        print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")
        msg_id += 1

    assert node1.state == "Error Passive", "Node 1 did not transition to ERROR_PASSIVE."
    print(f"Node 1 state after 16 errors: {node1.state}")

    for _ in range(16): #we were at 128 so 128 + (16 * 8) = 256 > 255 -> node should go in Bus Off at the end of this for
        node1.send_message(message_id=msg_id, data=[0x01, 0x02], error_type="form_error")
        bus.simulate_step()
        print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
        print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
        print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")
        msg_id += 1

    assert node1.state == "Bus Off", "Node 1 did not transition to BUS_OFF."
    print(f"Node 1 state after reaching BUS_OFF: {node1.state}")

    print("Trying to send message from node 1 (it is in bus off state now)")
    node1.send_message(message_id=msg_id, data=[0x01, 0x02])
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

    msg_id = msg_id + 1
    node2.send_message(message_id=msg_id, data=[0x03, 0x05])
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

    node3.send_message(message_id=msg_id, data=[0x03, 0x05])
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

    node1.transmit_error_counter = 8 
    node1.state = ERROR_ACTIVE
    node1.send_message(message_id=msg_id, data=[0x03, 0x05])
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node3.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

def test_retransmissions():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=106, data=[0x01, 0x02], error_type="bit_error")
    bus.simulate_step()

    assert node1.has_pending_message(), "Message was not retransmitted after error."
    print("Retransmission Test Passed.")

def test_simple_frame_transmission():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=200, data=[0xAA, 0xBB])
    bus.simulate_step()

    node2.send_message(message_id=201, frame_type="remote")
    bus.simulate_step()

    node3.send_message(frame_type="error")
    bus.simulate_step()
    print(f"{node3.transmit_error_counter}")

    node1.send_message(frame_type="overload")
    bus.simulate_step()

    print("Simple Frame Transmission Test Passed.")

def test_sequential_transmission():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=300, data=[0x11, 0x22])
    bus.simulate_step()

    node2.send_message(message_id=301, data=[0x33, 0x44])
    bus.simulate_step()

    node3.send_message(message_id=302, data=[0x55, 0x66])
    bus.simulate_step()

    print("Sequential Transmission Test Passed.")

def test_arbitration():
    bus, node1, node2, node3 = setup_can_network()

    node1.send_message(message_id=400, data=[0x01, 0x02])
    node2.send_message(message_id=401, data=[0x03, 0x04])
    node3.send_message(message_id=399, data=[0x05, 0x06]) 

    nodes_with_messages = [node for node in [node1, node2, node3] if node.has_pending_message()]
    winner_node = bus.perform_arbitration(nodes_with_messages)

    assert winner_node == node3, "Node 3 did not win arbitration."
    assert node3.mode == "transmitting", f"Node 3 mode: {node3.mode}. Expected: 'transmitting'."
    assert node1.mode == "receiving", f"Node 1 mode: {node1.mode}. Expected: 'receiving'."
    assert node2.mode == "receiving", f"Node 2 mode: {node2.mode}. Expected: 'receiving'."

    bus.deliver_message(winner_node)

    bus.simulate_step()
    bus.simulate_step()

    print("Arbitration Test Passed.")

def test_stuffing_and_form_errors():
    bus = CANBus()
    node1 = CANNode(node_id=1)
    node2 = CANNode(node_id=2)
    node3 = CANNode(node_id=3)

    bus.connect_node(node1)
    bus.connect_node(node2)
    bus.connect_node(node3)

    print("Testing Stuffing Error")
    node1.send_message(message_id=101, data=[0x00, 0x02], frame_type="data", error_type="stuff_error")
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")
    node1.message_queue.pop(0)

    #not resetting them to show the tec and rec increases accordingly
    # node1.transmit_error_counter = 0
    # node2.receive_error_counter = 0
    # node3.receive_error_counter = 0

    # Test Form Error
    print("Testing Form Error")
    node2.send_message(message_id=101, data=[0x03, 0x00], frame_type="data", error_type="form_error")
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")
    node2.message_queue.pop(0)

    print("Sending correct message xxx")
    node2.send_message(message_id=103, data=[0x01, 0x02], frame_type="data", error_type=None)
    bus.simulate_step()
    print(f"Node 1: REC={node1.receive_error_counter}, TEC={node1.transmit_error_counter}")
    print(f"Node 2: REC={node2.receive_error_counter}, TEC={node2.transmit_error_counter}")
    print(f"Node 3: REC={node3.receive_error_counter}, TEC={node3.transmit_error_counter}")

if __name__ == "__main__":
    print("Starting CAN Simulation Tests...")
    test_simple_frame_transmission()
    test_sequential_transmission()
    test_arbitration()
    test_ack_error_detection()
    test_crc_error_detection()
    test_bit_error_detection()
    #print("a ajuns aici")
    test_stuffing_and_form_errors()
    #test_state_transitions()
