from can_bus import CANBus
from can_node import CANNode

def main():
    bus = CANBus()

    bus = CANBus()

    node1 = CANNode(node_id=1)
    node2 = CANNode(node_id=2)
    node3 = CANNode(node_id=3)

    bus.add_node(node1)
    bus.add_node(node2)
    bus.add_node(node3)

    node1.send_message(0x100, data=[0x12, 0x34])
    node2.send_message(0x080, data=[0x56, 0x78])  #higher priority id
    node3.send_message(0x180, data=[0x9A, 0xBC])

    bus.transmit()


if __name__ == "__main__":
    main()