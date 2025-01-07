# # can_bus.py

# from can_node import CANNode, WAITING, TRANSMITTING, RECEIVING, BUS_OFF
# from can_message import DataFrame, ErrorFrame, OverloadFrame, RemoteFrame, CANMessage
# import random
# import time

# IDLE = "Idle"
# BUSY = "Busy"
# WAITING_ACK = "Waiting for ACK"

# class CANBus:
#     def __init__(self):
#         self.nodes = []
#         self.current_bit = 1  # default bit sent on the bus
#         self.in_arbitration = False
#         self.error = False
#         self.transmission_queue = []
#         self.current_bitstream = []
#         self.bitstream_display = []
#         self.state = IDLE
#         self.error_reported = False
#         self.overload_request = False

#         self.arbitration_in_progress = False
#         self.arbitration_bit_index = 0
#         self.current_winner = None
#         self.arbitration_contenders = []

#     def connect_node(self, node):
#         self.nodes.append(node)
#         node.set_bus(self)
#         print(f"Node {node.node_id} connected to the bus.")

#     def get_current_bit(self):
#         return self.current_bit

#     def simulate_step(self):
#         """
#         1) no current_winner or not arbitration_in_progress => find active nodes (nodes that have pending messages but are not BUS_OFF)
#            a. 0 => idle;
#            b. 1 => winner found;
#            c. >1 => start arbitration to find one winner;
#         2) arbitration_in_progress => do_one_arbitration_bit()
#         3) self.current_winner is diff then None => transmit_one_data_bit()
#            If done => finalize
#         """
#         self.current_bitstream.clear()
#         self.bitstream_display.clear()

#         if self.state == IDLE:
#             for nd in self.nodes:
#                 if nd.state != BUS_OFF:
#                     nd.mode = WAITING

#         # 1)
#         if not self.current_winner and not self.arbitration_in_progress:
#             active_nodes = [n for n in self.nodes if n.has_pending_message() and n.state != BUS_OFF]
#             # a.
#             if not active_nodes:
#                 print("No nodes with pending messages => bus idle => bit=1")
#                 self.current_bit = 1
#                 self.state = IDLE
#                 return

#             # b.
#             if len(active_nodes) == 1:
#                 self.current_winner = active_nodes[0]
#                 self.arbitration_in_progress = False
#                 self.in_arbitration = False
#                 self.arbitration_bit_index = 0
#                 self.state = BUSY

#                 for nd in self.nodes:
#                     if nd != self.current_winner and nd.state != BUS_OFF:
#                         nd.mode = RECEIVING
#             # c.
#             else:
#                 self.arbitration_contenders = active_nodes[:]
#                 self.arbitration_in_progress = True
#                 self.in_arbitration = True
#                 self.arbitration_bit_index = 0
#                 self.state = BUSY
#                 for nd in self.nodes:
#                     if nd in self.arbitration_contenders and nd.state != BUS_OFF:
#                         nd.mode = TRANSMITTING
#                     elif nd.state != BUS_OFF:
#                         nd.mode = RECEIVING

#                 print(f"Starting arbitration among {[nd.node_id for nd in self.arbitration_contenders]}")

#         # 2)
#         if self.arbitration_in_progress and not self.current_winner:
#             self.do_one_arbitration_bit()

#         # 3)
#         if self.current_winner:
#             self.transmit_one_data_bit(self.current_winner)
#             if self.current_winner.is_transmission_complete():
#                 print(f"Node {self.current_winner.node_id} => completed message.")
#                 self.finalize_message(self.current_winner)
#                 self.current_winner = None
#                 self.arbitration_in_progress = False
#                 self.in_arbitration = False
#                 self.arbitration_bit_index = 0
#                 self.arbitration_contenders.clear()
#                 self.state = IDLE

#     def do_one_arbitration_bit(self):
#         if self.arbitration_bit_index == 0:
#             self.current_bit = 0  # SOF=0
#             self.arbitration_bit_index = 1
#             print("Arbitration started (SOF=0).")
#             return

#         if self.arbitration_bit_index > 12:
#             self.current_winner = self.arbitration_contenders[0]
#             print(f"Arbitration done => forced winner Node {self.current_winner.node_id}")
#             self.arbitration_in_progress = False
#             return

#         bits_from_nodes = []
#         for nd in self.arbitration_contenders:
#             msg = nd.message_queue[0]
#             bs = msg.get_bitstream()
#             if self.arbitration_bit_index < len(bs):
#                 bit = bs[self.arbitration_bit_index]
#             else: #wont be the case but still
#                 bit = 1 
#             bits_from_nodes.append((nd, bit))

#         bit_values = [val for (n,val) in bits_from_nodes]
#         dominant_bit = min(bit_values)
#         self.current_bit = dominant_bit

#         new_contenders = []
#         for (nd, val) in bits_from_nodes:
#             if val == dominant_bit:
#                 new_contenders.append(nd)
#             else:
#                 nd.mode = RECEIVING  # lost arbitration

#         remain_ids = [nd.node_id for nd in new_contenders]
#         print(f"Arbitration bit {self.arbitration_bit_index}: {dominant_bit}, remain={remain_ids}")

#         if len(new_contenders) == 1:
#             self.current_winner = new_contenders[0]
#             print(f"Arbitration done => Node {self.current_winner.node_id} won.")
#             self.arbitration_in_progress = False
#             self.in_arbitration = False
#             self.current_winner.current_bit_index = self.arbitration_bit_index +1
#             self.arbitration_contenders.clear()
#             self.arbitration_bit_index = 0
#         else:
#             self.arbitration_contenders = new_contenders
#             self.arbitration_bit_index += 1

#     def transmit_one_data_bit(self, node):
#         if node.state == BUS_OFF:
#             return
#         node.mode = TRANSMITTING
#         bit = node.transmit_bit()
#         if bit is None:
#             self.current_bit = 1
#             return

#         self.current_bit = bit
#         print(f"Node {node.node_id} => data bit {node.current_bit_index -1} = {bit}")

#         msg = node.message_queue[0]
#         for nd in self.nodes:
#             if nd != node and nd.state != BUS_OFF:
#                 nd.process_received_bit(msg, node)

#         ack_idx = msg.get_ack_index()
#         if (node.current_bit_index) == ack_idx:
#             if msg.error_type == "ack_error":
#                 msg.ack_slot = 1 
#                 #print(f"ACK Error => ack_slot stays 1.")
#             else:
#                 msg.ack_slot = 0  # normal ack if no problem 

#     def finalize_message(self, node):
#         if not node.message_queue:
#             return
        
#         # if isinstance(node.message_queue[0], ErrorFrame):
#         #     for node_inc in self.nodes:
#         #         if node_inc.mode == RECEIVING:
#         #             if node.message_queue[0].error_type == "ack_error":
#         #                 node_inc.increment_receive_error()
#         #         elif node_inc.mode == TRANSMITTING:
#         #             node_inc.increment_transmit_error()            

#         msg = node.message_queue[0]
#         node.message_queue.pop(0)
#         node.stop_transmitting()

#         # decrement counters because no error 
#         if msg.error_type is None and isinstance(msg, (DataFrame, RemoteFrame)):
#             node.decrement_transmit_error()
#             for nd in self.nodes:
#                 if nd != node and nd.state != BUS_OFF and nd.mode == RECEIVING:
#                     nd.decrement_receive_error()

#         for nd in self.nodes:
#             if nd.state != BUS_OFF:
#                 nd.mode = WAITING
        
#         if msg.error_type != None and node.state != BUS_OFF and msg.error_type != "form_error":
#             #add the msg back if there was an error at the end of the queue
#             #if msg.retransmit_error and msg.error_type != "form_error": 
#             node.message_queue.append(msg)

#         self.current_winner = None
#         if isinstance(msg, RemoteFrame):
#             self.overload_request = False
#         elif isinstance(msg, ErrorFrame):
#             self.error_reported = False

#     # def broadcast_error_frame(self, error_type, message=None):
#     #     if self.error_reported:
#     #         return

#     #     reporter_node = None

#     #     if error_type == "bit_error" or error_type == "ack_error":
#     #         for nd in self.nodes:
#     #             if nd.mode == TRANSMITTING and nd.state != BUS_OFF:
#     #                 reporter_node = nd
#     #                 #reporter_node.
#     #                 break
#     #     else: 
#     #         listening_nodes = [x for x in self.nodes if x.mode == RECEIVING and x.state != BUS_OFF]
#     #         if listening_nodes:
#     #             reporter_node = random.choice(listening_nodes)
#     #         else:
#     #             reporter_node = random.choice([x for x in self.nodes if x.mode == TRANSMITTING and x.state != BUS_OFF])

#     #     if not reporter_node:
#     #         print("No valid reporter node found for error frame => skipping.")
#     #         return

#     #     print(f"Node {reporter_node.node_id} => broadcasting error frame: {error_type}")
        
#     #     # increment counters bc of the errors; maybe should od it after the error frame is transmitted? TODO!!! ✔️
#     #     for nd in self.nodes:
#     #         if nd.state == BUS_OFF:
#     #             continue
#     #         if nd == reporter_node and nd.mode == TRANSMITTING:
#     #             nd.increment_transmit_error()
#     #             nd.current_bit_index = 0
#     #             reporter_node.message_queue.pop(0)
#     #         elif nd.mode == RECEIVING:
#     #             nd.increment_receive_error()
#     #             pass

#     #     err_frame = ErrorFrame(sent_by=reporter_node.node_id)
#     #     reporter_node.message_queue.insert(0, err_frame)
#     #     self.current_winner = reporter_node
#     #     print(f"Node {reporter_node.node_id} => Error frame inserted => future partial sending.")
#     #     print(f"{reporter_node.node_id} => {reporter_node.message_queue[0]}")

#     #     for nd in self.nodes:
#     #         if nd.state != BUS_OFF:
#     #             if nd == reporter_node:
#     #                 nd.mode = TRANSMITTING
#     #             else:
#     #                 nd.mode = RECEIVING

#     #     self.error_reported = True
#     #     self.state = BUSY

#     def broadcast_error_frame(self, error_type, message=None):
#         if self.error_reported:
#             return

#         reporter_node = None
#         retransmittable_errors = {"ack_error", "bit_error", "crc_error", "stuff_error"}

#         # 1) Identify the 'reporter_node':
#         #    - bit_error/ack_error => typically the transmitter sees it first.
#         #    - stuff_error/crc_error/form_error => typically one of the receivers sees it.
#         if error_type in ("bit_error", "ack_error"):
#             # Typically the transmitter is the one that detects these errors
#             for nd in self.nodes:
#                 if nd.mode == TRANSMITTING and nd.state != BUS_OFF:
#                     reporter_node = nd
#                     break
#         else:
#             # Typically a receiver detects stuff_error, crc_error, or form_error
#             listening_nodes = [
#                 x for x in self.nodes 
#                 if x.mode == RECEIVING and x.state != BUS_OFF
#             ]
#             if listening_nodes:
#                 reporter_node = random.choice(listening_nodes)
#             else:
#                 # fallback if no node is receiving
#                 transmitters = [
#                     x for x in self.nodes 
#                     if x.mode == TRANSMITTING and x.state != BUS_OFF
#                 ]
#                 if transmitters:
#                     reporter_node = random.choice(transmitters)

#         if not reporter_node:
#             print("No valid reporter node found for error frame => skipping.")
#             return

#         print(f"Node {reporter_node.node_id} => broadcasting error frame: {error_type}")

#         # 2) Create and insert an ErrorFrame at the front of the reporter_node queue.
#         err_frame = ErrorFrame(sent_by=reporter_node.node_id)
#         reporter_node.message_queue.insert(0, err_frame)

#         # 3) Force the actual transmitter(s) to abort their current (faulty) message
#         #    and increment TX errors.
#         #    - If the reporter_node is the one transmitting (e.g. bit/ack error),
#         #      it's included here.
#         #    - If a different node was transmitting a faulty message,
#         #      that node also stops.
#         #    - We also remove the "bad" message from that node's queue (optional).
#         for nd in self.nodes:
#             if nd.state == BUS_OFF:
#                 continue

#             if nd.mode == TRANSMITTING:
#                 # This node is currently sending the faulty message
#                 nd.increment_transmit_error()
#                 nd.stop_transmitting()
#                 # Remove that faulty message from the queue so it won't keep sending
#                 if nd.message_queue and not isinstance(nd.message_queue[-1], ErrorFrame):
#                     faulty_msg = nd.message_queue.pop(-1)

#                     if error_type in retransmittable_errors:
#                         nd.current_bit_index = 0
#                         nd.message_queue.append(faulty_msg)

#         # 4) Increment receive errors for the receiving nodes that actually 'listen' to this message
#         #    (i.e., they have the message ID in their filters).
#         #    For a truly strict approach, we should also check if the node was actually receiving
#         #    at the time. (Here we just do it if the node is in RECEIVING mode.)
#         if message and hasattr(message, "identifier"):
#             for nd in self.nodes:
#                 if nd.state != BUS_OFF and nd.mode == RECEIVING:
#                     if message.identifier in nd.filters:
#                         nd.increment_receive_error()

#         self.current_winner = reporter_node
#         self.error_reported = True
#         self.state = BUSY

#         for nd in self.nodes:
#             if nd.state != BUS_OFF:
#                 if nd == reporter_node:
#                     nd.mode = TRANSMITTING
#                 else:
#                     nd.mode = RECEIVING

#         print(f"Node {reporter_node.node_id} => Error frame inserted => partial sending soon.")
#         print(f"{reporter_node.node_id} => {reporter_node.message_queue[0]}")

#     def broadcast_overload_frame(self, sender=None):
#         print("Broadcasting overload frame.")
#         if not sender:
#             active = [n for n in self.nodes if n.state!=BUS_OFF]
#             if not active:
#                 print("No node available for OverloadFrame.")
#                 return
#             sender = random.choice(active)

#         overload = OverloadFrame(sent_by=sender.node_id)
#         sender.message_queue.insert(0, overload)

#         for nd in self.nodes:
#             if nd.state!=BUS_OFF:
#                 if nd==sender:
#                     nd.mode=TRANSMITTING
#                 else:
#                     nd.mode=RECEIVING

#         self.current_winner = sender
#         self.overload_request = True
#         self.arbitration_in_progress = False
#         self.state = BUSY
#         print(f"Node {sender.node_id} => Overload frame inserted => future partial sending.")

#     def reset_nodes_after_error(self):
#         for nd in self.nodes:
#             if nd.state!=BUS_OFF:
#                 nd.mode = WAITING
#         self.state = IDLE

#     def reset_bus(self):
#         for nd in self.nodes:
#             nd.reset_node()
#         self.current_bit = 1
#         self.in_arbitration = False
#         self.error = False
#         self.transmission_queue.clear()
#         self.current_bitstream.clear()
#         self.bitstream_display.clear()
#         self.state = IDLE
#         self.error_reported = False
#         self.overload_request = False

#         self.arbitration_in_progress = False
#         self.arbitration_bit_index = 0
#         self.current_winner = None
#         self.arbitration_contenders.clear()


# can_bus.py

from can_node import CANNode, WAITING, TRANSMITTING, RECEIVING, BUS_OFF
from can_message import DataFrame, ErrorFrame, OverloadFrame, RemoteFrame
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
        1) if no current_winner and not arbitration_in_progress => find active nodes
           a) 0 => idle
           b) 1 => winner found
           c) >1 => start arbitration
        2) if arbitration_in_progress => do_one_arbitration_bit()
        3) if self.current_winner => transmit_one_data_bit()
           if done => finalize_message
        4) if the reporter/current_winner is BUS_OFF => release bus
        """
        self.current_bitstream.clear()
        self.bitstream_display.clear()

        # ### 1a) If we are IDLE, ensure all non-BUS_OFF nodes are WAITING
        if self.state == IDLE:
            for nd in self.nodes:
                if nd.state != BUS_OFF:
                    nd.mode = WAITING

        # ### 1b) If we have no winner and are not arbitrating, check for active nodes
        if not self.current_winner and not self.arbitration_in_progress:
            active_nodes = [n for n in self.nodes if n.has_pending_message() and n.state != BUS_OFF]

            if not active_nodes:
                # No nodes have pending messages => bus idle
                self.current_bit = 1
                self.state = IDLE
                print("No nodes with pending messages => bus idle => bit=1")
                return

            if len(active_nodes) == 1:
                # Exactly one node => it wins immediately
                self.current_winner = active_nodes[0]
                self.arbitration_in_progress = False
                self.in_arbitration = False
                self.arbitration_bit_index = 0
                self.state = BUSY

                for nd in self.nodes:
                    if nd != self.current_winner and nd.state != BUS_OFF:
                        nd.mode = RECEIVING
            else:
                # More than one => start arbitration
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

        # 2) Arbitration in progress?
        if self.arbitration_in_progress and not self.current_winner:
            self.do_one_arbitration_bit()

        # 3) If we have a winner, transmit a data bit
        if self.current_winner:
            # ### 3a) If the winner is BUS_OFF for some reason, drop it
            if self.current_winner.state == BUS_OFF:
                print(f"Winner node {self.current_winner.node_id} went BUS_OFF before/during transmission. Releasing the bus.")
                self.current_winner = None
                self.state = IDLE
                self.error_reported = False
                return

            self.transmit_one_data_bit(self.current_winner)
            if self.current_winner and self.current_winner.is_transmission_complete():
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
            else:
                bit = 1
            bits_from_nodes.append((nd, bit))

        bit_values = [val for (_, val) in bits_from_nodes]
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
            self.current_winner.current_bit_index = self.arbitration_bit_index + 1
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
        print(f"Node {node.node_id} => data bit {node.current_bit_index - 1} = {bit}")

        msg = node.message_queue[0]
        # Notify other nodes
        for nd in self.nodes:
            if nd != node and nd.state != BUS_OFF:
                nd.process_received_bit(msg, node)

        # Check ACK
        ack_idx = msg.get_ack_index()
        if (node.current_bit_index) == ack_idx:
            if msg.error_type == "ack_error":
                msg.ack_slot = 1
            else:
                msg.ack_slot = 0  # normal ack

    def finalize_message(self, node):
        """
        Remove the just-finished message from node's queue.
        Decrement error counters if no error. Possibly re-insert
        if error and re-transmission is desired.
        """
        if not node.message_queue:
            return

        msg = node.message_queue[0]
        node.message_queue.pop(0)
        node.stop_transmitting()

        if msg.error_type is None and isinstance(msg, (DataFrame, RemoteFrame)):
            # no error => decrement counters
            node.decrement_transmit_error()
            for nd in self.nodes:
                if nd != node and nd.state != BUS_OFF and nd.mode == RECEIVING:
                    nd.decrement_receive_error()

        # Let all non-BUS_OFF nodes go to WAITING
        for nd in self.nodes:
            if nd.state != BUS_OFF:
                nd.mode = WAITING

        # Possibly re-insert the message if it had some errors but not form_error
        if msg.error_type is not None and node.state != BUS_OFF and msg.error_type != "form_error":
            # only re-insert if your logic requires it
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
        retransmittable_errors = {"ack_error", "bit_error", "crc_error", "stuff_error"}

        if error_type in ("bit_error", "ack_error"):
            for nd in self.nodes:
                if nd.mode == TRANSMITTING and nd.state != BUS_OFF:
                    reporter_node = nd
                    break
        else:
            if message and hasattr(message, "identifier"):
                listening_nodes = [
                    x for x in self.nodes
                    if x.mode == RECEIVING and x.state != BUS_OFF and (message.identifier in x.filters)
                ]
            else:
                listening_nodes = [
                    x for x in self.nodes if x.mode == RECEIVING and x.state != BUS_OFF
                ]
            if listening_nodes:
                reporter_node = random.choice(listening_nodes)
            else:
                transmitters = [x for x in self.nodes if x.mode == TRANSMITTING and x.state != BUS_OFF]
                if transmitters:
                    reporter_node = random.choice(transmitters)

        if not reporter_node:
            print("No valid reporter node found for error frame => skipping.")
            return

        print(f"Node {reporter_node.node_id} => broadcasting error frame: {error_type}")

        err_frame = ErrorFrame(sent_by=reporter_node.node_id)
        reporter_node.message_queue.insert(0, err_frame)

        for nd in self.nodes:
            if nd.state == BUS_OFF:
                continue

            if nd.mode == TRANSMITTING:
                nd.increment_transmit_error()
                nd.stop_transmitting()
                if nd.message_queue and not isinstance(nd.message_queue[-1], ErrorFrame):
                    faulty_msg = nd.message_queue.pop(-1)
                    if error_type in retransmittable_errors:
                        nd.current_bit_index = 0
                        nd.message_queue.append(faulty_msg)

        if reporter_node.state == BUS_OFF:
            print(f"Reporter node {reporter_node.node_id} is now BUS_OFF => Aborting error frame transmission.")
            if reporter_node.message_queue and isinstance(reporter_node.message_queue[0], ErrorFrame):
                reporter_node.message_queue.pop(0)
            self.current_winner = None
            self.error_reported = False
            self.state = IDLE
            return

        # 4) Increment receive error counters for nodes that were actually listening
        if message and hasattr(message, "identifier"):
            for nd in self.nodes:
                if nd.state != BUS_OFF and nd.mode == RECEIVING:
                    if message.identifier in nd.filters:
                        nd.increment_receive_error()

        self.current_winner = reporter_node
        self.error_reported = True
        self.state = BUSY

        for nd in self.nodes:
            if nd.state != BUS_OFF:
                if nd == reporter_node:
                    nd.mode = TRANSMITTING
                else:
                    nd.mode = RECEIVING

        print(f"Node {reporter_node.node_id} => Error frame inserted => partial sending soon.")
        print(f"{reporter_node.node_id} => {reporter_node.message_queue[0]}")

    def broadcast_overload_frame(self, sender=None):
        print("Broadcasting overload frame.")
        if not sender:
            active = [n for n in self.nodes if n.state != BUS_OFF]
            if not active:
                print("No node available for OverloadFrame.")
                return
            sender = random.choice(active)

        overload = OverloadFrame(sent_by=sender.node_id)
        sender.message_queue.insert(0, overload)

        for nd in self.nodes:
            if nd.state != BUS_OFF:
                if nd == sender:
                    nd.mode = TRANSMITTING
                else:
                    nd.mode = RECEIVING

        self.current_winner = sender
        self.overload_request = True
        self.arbitration_in_progress = False
        self.state = BUSY
        print(f"Node {sender.node_id} => Overload frame inserted => future partial sending.")

    def reset_nodes_after_error(self):
        for nd in self.nodes:
            if nd.state != BUS_OFF:
                nd.mode = WAITING
        self.state = IDLE

    def reset_bus(self):
        for nd in self.nodes:
            nd.reset_node()
        self.current_bit = 1
        self.in_arbitration = False
        self.error = False
        self.transmission_queue.clear()
        self.current_bitstream.clear()
        self.bitstream_display.clear()
        self.state = IDLE
        self.error_reported = False
        self.overload_request = False

        self.arbitration_in_progress = False
        self.arbitration_bit_index = 0
        self.current_winner = None
        self.arbitration_contenders.clear()
