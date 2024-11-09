from can_bus import CANBus
from can_node import CANNode

def main():
    bus = CANBus()

    node1 = CANNode(1)
    node2 = CANNode(2)
    node3 = CANNode(3)

    bus.add_node(node1)
    bus.add_node(node2)
    bus.add_node(node3)

    print("\n--- Queueing Messages for Arbitration Test ---")
    node1.send_message(20, "Message from Node 1")
    node2.send_message(40, "Message from Node 2") 
    node3.send_message(10, "Message from Node 3") 
    print("\nFirst Transmission: 3 messages to be sent")
    bus.transmit()

    print("\nSecond Transmission: 1 message to be sent")
    node1.send_message(10, "Only one message")
    bus.transmit()

    print("\nThird Transmission: no messages to be sent")
    bus.transmit()

if __name__ == "__main__":
    main()