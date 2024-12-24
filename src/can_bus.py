# can_bus.py
from can_node import CANNode, WAITING, TRANSMITTING, RECEIVING, BUS_OFF 
from can_message import DataFrame, ErrorFrame, OverloadFrame, RemoteFrame, CANMessage
import random 
import time

IDLE = "Idle"
BUSY = "Busy"
WAITING_ACK = "Waiting for ACK"

class CANBus:
    def __init__(self):
        self.nodes = []  
        self.current_bit = 1  # By default, the current bit that is sent is 1 
        self.in_arbitration = False  
        self.error = False
        self.transmission_queue = []
        self.current_bitstream = [] 
        self.bitstream_display = []  # Using this for the simulation 
        self.state = IDLE 
        self.error_reported = False
        self.arbitration_in_progress = False
        self.arbitration_bit_index = 0
        self.current_winner = None
        self.arbitration_contenders = []
    
    def connect_node(self, node):
        self.nodes.append(node)
        node.set_bus(self)
        print(f"Node {node.node_id} connected to the bus.")

    def get_current_bit(self):
        return self.current_bit

    def simulate_step(self):
        """
        Called once per 'clock tick' => send exactly ONE bit.
        
        Steps:
          1) If we do NOT have a current_winner or arbitration_in_progress,
             gather active nodes (with pending messages + not BUS_OFF).
             - If none => bus idle
             - If exactly 1 => that is the winner
             - Else => start arbitration
          2) If arbitration_in_progress => do_one_arbitration_bit()
          3) If current_winner => transmit_one_data_bit()
             - if done => finalize
        """
        # Clear old step’s bit info
        self.current_bitstream.clear()
        self.bitstream_display.clear()

        # 1) If no current winner & not in arbitration => gather active nodes
        if not self.current_winner and not self.arbitration_in_progress:
            active_nodes = [n for n in self.nodes if n.has_pending_message() and n.state != BUS_OFF]
            if not active_nodes:
                # no messages => idle
                print("No nodes with pending messages => Bus is IDLE.")
                self.state = IDLE
                self.current_bit = 1
                return

            if len(active_nodes) == 1:
                # single => immediate winner
                self.current_winner = active_nodes[0]
                self.arbitration_in_progress = False
                self.in_arbitration = False
                self.arbitration_bit_index = 0
                self.state = BUSY

                for node in self.nodes:
                    if node != self.current_winner and node.mode != BUS_OFF:
                        node.mode = RECEIVING
            else:
                # multiple => start arbitration
                self.arbitration_contenders = active_nodes[:]
                self.arbitration_in_progress = True
                self.in_arbitration = True
                self.arbitration_bit_index = 0
                self.state = BUSY
                for node in self.nodes:
                    if node not in self.arbitration_contenders and node.mode != BUS_OFF:
                        node.mode = RECEIVING
                    else:
                        node.mode = TRANSMITTING
                ids = [n.node_id for n in self.arbitration_contenders]
                print(f"Starting arbitration among {ids}")

        # 2) If arbitration_in_progress & no winner => do one arbitration bit
        if self.arbitration_in_progress and not self.current_winner:
            self.do_one_arbitration_bit()

        # 3) If we have a winner => transmit one data bit
        if self.current_winner:
            self.transmit_one_data_bit(self.current_winner)

            # if finished => finalize
            if self.current_winner.is_transmission_complete():
                print(f"Node {self.current_winner.node_id} completed message.")
                self.finalize_message(self.current_winner)
                # reset
                self.current_winner = None
                self.arbitration_in_progress = False
                self.in_arbitration = False
                self.arbitration_bit_index = 0
                self.arbitration_contenders.clear()
                self.state = IDLE

    def do_one_arbitration_bit(self):
        """
        Perform 1 arbitration bit among self.arbitration_contenders.
         - If exactly 1 remains => current_winner
         - If multiple remain => increment arbitration_bit_index
         - If bit_index > 12 => forcibly pick first
        """
        # The first arbitration bit => SOF=0
        if self.arbitration_bit_index == 0:
            self.current_bit = 0
            self.arbitration_bit_index = 1
            print("Arbitration started (SOF=0).")
            return

        # If we exceed 12 bits => forcibly pick the first
        if self.arbitration_bit_index > 12:
            self.current_winner = self.arbitration_contenders[0]
            print(f"Arbitration done. Node {self.current_winner.node_id} won (forced).")
            self.arbitration_in_progress = False
            return

        # For each contender => get the bit at arbitration_bit_index
        bits_from_nodes = []
        for node in self.arbitration_contenders:
            msg = node.message_queue[0]
            bs = msg.get_bitstream()
            if self.arbitration_bit_index < len(bs):
                bit = bs[self.arbitration_bit_index]
            else:
                bit = 1  # if out-of-range => recessive
            bits_from_nodes.append((node, bit))

        # Determine dominant bit
        bit_values = [bit for (n, bit) in bits_from_nodes]
        dominant_bit = min(bit_values)  # 0 is dominant

        # Keep only the nodes that sent dominant_bit; losers => mode=RECEIVING
        new_list = []
        for (node, val) in bits_from_nodes:
            if val == dominant_bit:
                new_list.append(node)
            else:
                node.mode = RECEIVING  # lost arbitration

        self.current_bit = dominant_bit

        # Debug
        remain_ids = [n.node_id for n in new_list]
        print(f"Arbitration bit {self.arbitration_bit_index}: {dominant_bit}; remain={remain_ids}")

        if len(new_list) == 1:
            # winner
            self.current_winner = new_list[0]
            self.arbitration_contenders.clear()
            print(f"Arbitration done. Node {self.current_winner.node_id} won.")
            self.arbitration_in_progress = False
            self.in_arbitration = False
            self.current_winner.current_bit_index = self.arbitration_bit_index + 1
            #self.current_bit_index = self.arbitration_bit_index + 1
            self.arbitration_bit_index = 0
        else:
            self.arbitration_contenders = new_list
            self.arbitration_bit_index += 1

    def transmit_one_data_bit(self, node):
        """
        Transmit exactly 1 data bit from node's message.
        Check for errors bit-by-bit (bit_error, ack_error, etc.).
        If we see an error => broadcast error, increment counters, node -> WAITING.
        Also handle the ACK slot if we reached that bit index => set ack_slot=0 if no ack error.
        """
        node.mode = TRANSMITTING
        bit = node.transmit_bit()
        if bit is None:
            # either done or error
            self.current_bit = 1
            return

        # set bus current bit
        self.current_bit = bit

        # Debug:
        print(f"Node {node.node_id} => bus bit {node.current_bit_index -1} = {bit}")

        # Deliver this bit to others
        for other in self.nodes:
            if other != node:
                other.process_received_bit(node.message_queue[0], node)

        # Check if this bit is the "ACK slot"
        msg = node.message_queue[0]
        ack_index = msg.get_ack_index()  # bit index for ACK slot
        # node.current_bit_index-1 is the bit we *just* transmitted
        if (node.current_bit_index -1) == ack_index:
            # If there's no ack_error => set ack_slot=0
            # If there *is* ack_error => it's already set to 1 in can_message
            if msg.error_type == "ack_error":
                print("ACK Error => ack_slot remains 1.")
            else:
                msg.ack_slot = 0  # normal ACK

        # Also check if this bit is error_bit_index for bit_error, stuff_error, etc. 
        # But usually that logic is in the node's transmit_bit() or process_received_bit().
        # We can do a final check here, e.g. if node.current_bit_index-1 == message.error_bit_index:
        #    handle it.  But let's keep it in the node’s code or process_received_bit.

    def finalize_message(self, node):
        """
        Once a node finishes transmitting => pop from queue, reset mode, done.
        """
        print("finish1")
        print(f"Node msg queue: {node.message_queue}")
        if node.message_queue[0].error_type == None:
            if isinstance(node.message_queue[0], DataFrame) or isinstance(node.message_queue[0], RemoteFrame):
                for node in self.nodes:
                    if node.mode == TRANSMITTING:
                        node.transmit_error_counter -= 1
                    elif node.mode == RECEIVING:
                        node.receive_error_counter -= 1
        print(f"Node msg queue: {node.message_queue}")
        msg = node.message_queue[0]
        node.message_queue.pop(0)
        node.stop_transmitting()
        print(f"Node {node.node_id} finished sending {msg} => node WAITING.")
        for nodes in self.nodes:
            nodes.mode = WAITING

        self.error_reported = False

    def broadcast_error_frame(self, error_type, message=None):
        if self.error_reported:
            return 
        
        eligible_receivers = [node for node in self.nodes if node.mode == RECEIVING and node.state != BUS_OFF]
        for node in self.nodes:
            if node.mode == TRANSMITTING:
                sender_node = node
                break
        print(f"Sender node: {sender_node.node_id}")
        #sender_node = sender_node[0] if sender_node else None
        self.current_bitstream.clear()
        self.bitstream_display.clear()

        print("here1")
        if error_type == "bit_error" and message:
            reporter_node = sender_node 
            print("here2")
            print(f"Node {sender_node.node_id} detected a Bit Monitoring Error at Bit {message.error_bit_index}.")
            print(f"Broadcasting error frame for bit error.")
        elif eligible_receivers:
            reporter_node = random.choice(eligible_receivers)
            if message:
                print(f"Node {reporter_node.node_id} detected the {error_type} error in the message {message.identifier} and is reporting it.")
                print(f"Broadcasting error frame for {error_type}.")
            else: 
                print(f"Node {reporter_node.node_id} detected a generic error and is reporting it.")
                print(f"Broadcasting error frame.")

        # Increment error counters based on node modes
        print("here3")
        for node in self.nodes:
            if node.mode == RECEIVING:
                node.increment_receive_error()
                print(f"Node {node.node_id} -> TEC: {node.transmit_error_counter}; REC: {node.receive_error_counter}")
            elif node.mode == TRANSMITTING:
                node.increment_transmit_error()
                print(f"Node {node.node_id} -> TEC: {node.transmit_error_counter}; REC: {node.receive_error_counter}")

        self.error_reported = True
        self.reset_nodes_after_error()
        print("here4")
        if sender_node:
            sender_node.stop_transmitting()

        for node in self.nodes:
            node.mode = WAITING

        print("here5")
        self.current_winner = reporter_node
        self.state = BUSY

        # Transmit the ErrorFrame
        print("here6")
        error_frame = ErrorFrame(sent_by=reporter_node)
        reporter_node.message_queue.insert(0, error_frame)
        print(f"message queue: {reporter_node.message_queue}")

    def reset_nodes_after_error(self):
        for node in self.nodes:
            node.mode = WAITING
        self.state = IDLE

    def broadcast_overload_frame(self, sender=None):
        print("Broadcasting overload frame.")
        if not sender:
            sender = random.choice(self.nodes) 
            while sender.mode == BUS_OFF:
                sender = random.choice(self.nodes)

        overload_frame = OverloadFrame(sent_by=sender)
        sender.message_queue.insert(0, overload_frame)
        for node in self.nodes:
            node.handle_overload_frame()
        print("Overload frame processing complete.")
