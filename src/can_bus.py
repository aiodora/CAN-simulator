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
        self.current_bit = 1  # default bit sent on the bus
        self.in_arbitration = False
        self.error = False
        self.transmission_queue = []
        self.current_bitstream = []
        self.bitstream_display = []
        self.state = IDLE
        self.error_reported = False
        self.overload_request = False

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
        1) no current_winner or not arbitration_in_progress => find active nodes (nodes that have pending messages but are not BUS_OFF)
           a. 0 => idle;
           b. 1 => winner found;
           c. >1 => start arbitration to find one winner;
        2) arbitration_in_progress => do_one_arbitration_bit()
        3) self.current_winner is diff then None => transmit_one_data_bit()
           If done => finalize
        """
        self.current_bitstream.clear()
        self.bitstream_display.clear()

        # 1)
        if not self.current_winner and not self.arbitration_in_progress:
            active_nodes = [n for n in self.nodes if n.has_pending_message() and n.state != BUS_OFF]
            # a.
            if not active_nodes:
                print("No nodes with pending messages => bus idle => bit=1")
                self.current_bit = 1
                self.state = IDLE
                return

            # b.
            if len(active_nodes) == 1:
                self.current_winner = active_nodes[0]
                self.arbitration_in_progress = False
                self.in_arbitration = False
                self.arbitration_bit_index = 0
                self.state = BUSY

                for nd in self.nodes:
                    if nd != self.current_winner and nd.state != BUS_OFF:
                        nd.mode = RECEIVING
            # c.
            else:
                self.arbitration_contenders = active_nodes[:]
                self.arbitration_in_progress = True
                self.in_arbitration = True
                self.arbitration_bit_index = 0
                self.state = BUSY
                for nd in self.nodes:
                    if nd in self.arbitration_contenders and nd.state != BUS_OFF:
                        nd.mode = TRANSMITTING
                    elif nd.state != BUS_OFF:
                        nd.mode = RECEIVING

                print(f"Starting arbitration among {[nd.node_id for nd in self.arbitration_contenders]}")

        # 2)
        if self.arbitration_in_progress and not self.current_winner:
            self.do_one_arbitration_bit()

        # 3)
        if self.current_winner:
            self.transmit_one_data_bit(self.current_winner)
            if self.current_winner.is_transmission_complete():
                print(f"Node {self.current_winner.node_id} => completed message.")
                self.finalize_message(self.current_winner)
                self.current_winner = None
                self.arbitration_in_progress = False
                self.in_arbitration = False
                self.arbitration_bit_index = 0
                self.arbitration_contenders.clear()
                self.state = IDLE

    def do_one_arbitration_bit(self):
        if self.arbitration_bit_index == 0:
            self.current_bit = 0  # SOF=0
            self.arbitration_bit_index = 1
            print("Arbitration started (SOF=0).")
            return

        if self.arbitration_bit_index > 12:
            self.current_winner = self.arbitration_contenders[0]
            print(f"Arbitration done => forced winner Node {self.current_winner.node_id}")
            self.arbitration_in_progress = False
            return

        bits_from_nodes = []
        for nd in self.arbitration_contenders:
            msg = nd.message_queue[0]
            bs = msg.get_bitstream()
            if self.arbitration_bit_index < len(bs):
                bit = bs[self.arbitration_bit_index]
            else: #wont be the case but still
                bit = 1 
            bits_from_nodes.append((nd, bit))

        bit_values = [val for (n,val) in bits_from_nodes]
        dominant_bit = min(bit_values)
        self.current_bit = dominant_bit

        new_contenders = []
        for (nd, val) in bits_from_nodes:
            if val == dominant_bit:
                new_contenders.append(nd)
            else:
                nd.mode = RECEIVING  # lost arbitration

        remain_ids = [nd.node_id for nd in new_contenders]
        print(f"Arbitration bit {self.arbitration_bit_index}: {dominant_bit}, remain={remain_ids}")

        if len(new_contenders) == 1:
            self.current_winner = new_contenders[0]
            print(f"Arbitration done => Node {self.current_winner.node_id} won.")
            self.arbitration_in_progress = False
            self.in_arbitration = False
            self.current_winner.current_bit_index = self.arbitration_bit_index +1
            self.arbitration_contenders.clear()
            self.arbitration_bit_index = 0
        else:
            self.arbitration_contenders = new_contenders
            self.arbitration_bit_index += 1

    def transmit_one_data_bit(self, node):
        if node.state == BUS_OFF:
            return
        node.mode = TRANSMITTING
        bit = node.transmit_bit()
        if bit is None:
            self.current_bit = 1
            return

        self.current_bit = bit
        print(f"Node {node.node_id} => data bit {node.current_bit_index -1} = {bit}")

        msg = node.message_queue[0]
        for nd in self.nodes:
            if nd != node and nd.state != BUS_OFF:
                nd.process_received_bit(msg, node)

        ack_idx = msg.get_ack_index()
        if (node.current_bit_index) == ack_idx:
            if msg.error_type == "ack_error":
                msg.ack_slot = 1 
                #print(f"ACK Error => ack_slot stays 1.")
            else:
                msg.ack_slot = 0  # normal ack if no problem 
                print(f"Node {node.node_id} => ack_slot=0")

    def finalize_message(self, node):
        if not node.message_queue:
            return
        
        if isinstance(node.message_queue[0], ErrorFrame):
            for node_inc in self.nodes:
                if node_inc.mode == RECEIVING:
                    node_inc.increment_receive_error()
                elif node_inc.mode == TRANSMITTING:
                    node_inc.increment_transmit_error()            

        msg = node.message_queue[0]
        node.message_queue.pop(0)
        node.stop_transmitting()

        # decrement counters because no error 
        if msg.error_type is None and isinstance(msg, (DataFrame, RemoteFrame)):
            node.decrement_transmit_error()
            for nd in self.nodes:
                if nd != node and nd.state != BUS_OFF and nd.mode == RECEIVING:
                    nd.decrement_receive_error()

        print(f"bistream: {msg.get_bitstream()}")
        print(f"Node {node.node_id} => finished sending {msg}. Waiting now.")
        for nd in self.nodes:
            if nd.state != BUS_OFF:
                nd.mode = WAITING
        
        if msg.error_type != None and node.state != BUS_OFF:
            #add the msg back if there was an error at the end of the queue
            node.message_queue.append(msg)

        self.current_winner = None
        if isinstance(msg, RemoteFrame):
            self.overload_request = False
        elif isinstance(msg, ErrorFrame):
            self.error_reported = False

    def broadcast_error_frame(self, error_type, message=None):
        if self.error_reported:
            return

        reporter_node = None
        for nd in self.nodes:
            if nd.mode == TRANSMITTING and nd.state != BUS_OFF:
                reporter_node = nd
                break
        if not reporter_node and message: 
            if message.sender_id:
                fallback = [x for x in self.nodes if x.node_id==message.sender_id and x.state != BUS_OFF]
                if fallback:
                    reporter_node = fallback[0]
        if not reporter_node:
            listening_nodes = [x for x in self.nodes if x.mode == RECEIVING and x.state != BUS_OFF]
            if listening_nodes:
                reporter_node = random.choice(listening_nodes)

        if not reporter_node:
            print("No valid reporter node found for error frame => skipping.")
            return

        print(f"Node {reporter_node.node_id} => broadcasting error frame: {error_type}")
        
        # increment counters bc of the errors; maybe should od it after the error frame is transmitted? TODO!!!
        for nd in self.nodes:
            if nd.state == BUS_OFF:
                continue
            if nd == reporter_node and nd.mode == TRANSMITTING:
                #nd.increment_transmit_error()
                nd.current_bit_index = 0
            elif nd.mode == RECEIVING:
                #nd.increment_receive_error()
                pass

        err_frame = ErrorFrame(sent_by=reporter_node.node_id)
        reporter_node.message_queue.insert(0, err_frame)
        self.current_winner = reporter_node

        for nd in self.nodes:
            if nd.state != BUS_OFF:
                if nd == reporter_node:
                    nd.mode = TRANSMITTING
                else:
                    nd.mode = RECEIVING

        self.error_reported = True
        self.state = BUSY

    def broadcast_overload_frame(self, sender=None):
        print("Broadcasting overload frame.")
        if not sender:
            active = [n for n in self.nodes if n.state!=BUS_OFF]
            if not active:
                print("No node available for OverloadFrame.")
                return
            sender = random.choice(active)

        overload = OverloadFrame(sent_by=sender.node_id)
        sender.message_queue.insert(0, overload)

        for nd in self.nodes:
            if nd.state!=BUS_OFF:
                if nd==sender:
                    nd.mode=TRANSMITTING
                else:
                    nd.mode=RECEIVING

        self.current_winner = sender
        self.overload_request = True
        self.arbitration_in_progress = False
        self.state = BUSY
        print(f"Node {sender.node_id} => Overload frame inserted => future partial sending.")

    def reset_nodes_after_error(self):
        for nd in self.nodes:
            if nd.state!=BUS_OFF:
                nd.mode = WAITING
        self.state = IDLE
