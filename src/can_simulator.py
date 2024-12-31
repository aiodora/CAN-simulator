import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from tkinter import HORIZONTAL, simpledialog
import tkinter as tk
import random
import time

from can_bus import CANBus
from can_node import CANNode, TRANSMITTING, RECEIVING, WAITING, BUS_OFF, ERROR_PASSIVE, ERROR_ACTIVE
from can_message import CANMessage, DataFrame, RemoteFrame, ErrorFrame, OverloadFrame

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

COMPONENTS = {
    "Control Unit": {"id_range": (0, 511), "listens_to": ["Control Unit", "Sensors", "Actuators"]},
    "Power Supply Unit": {"id_range": (512, 1023), "listens_to": ["Control Unit", "Power Supply Unit", "Sensors"]},
    "Sensors": {"id_range": (1024, 1535), "listens_to": ["Control Unit", "Sensors", "Actuators"]},
    "Actuators": {"id_range": (1536, 2047), "listens_to": ["Control Unit", "Sensors"]},
}

class CANSimulatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CAN Simulator Project")
        self.geometry("1200x800")

        self.grid_rowconfigure(0, weight=4)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.playground = Playground(self, self)
        self.log_panel = LogPanel(self)
        self.predefined_scenarios = PredefinedScenarios(self, self.playground, self.log_panel)
        self.interactive_simulation = InteractiveSimulation(self, self.playground, self.log_panel)

        self.playground.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.log_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        self.show_predefined_scenarios()

    def show_predefined_scenarios(self):
        #reset everything 
        self.playground.reset()
        self.clear_scenario_frames()
        self.predefined_scenarios.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

    def show_interactive_simulation(self):
        self.playground.reset()
        self.clear_scenario_frames()
        self.interactive_simulation.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

    def clear_scenario_frames(self):
        self.predefined_scenarios.grid_remove()
        self.interactive_simulation.grid_remove()

class Playground(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.bus = CANBus()
        self.nodes = {}
        self.node_positions = {}
        self.node_visuals = {}
        self.node_info_labels = {}
        self.next_node_id = 1
        self.max_nodes = 50
        self.schedule_times = []

        self.clock_running = False
        self.clock = 0

        self.stuff_in = {}

        self.transmit_start_times = {}

        self.previous_frame = None
        self.previous_frame_type = None
        self.previous_error_type = None

        self.arbitration = "" 

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(self, bg="black", scrollregion=(0, 0, 2000, 1000))
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.scroll_x = ctk.CTkScrollbar(self, orientation=HORIZONTAL, command=self.canvas.xview)
        self.scroll_x.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.canvas.configure(xscrollcommand=self.scroll_x.set)

        self.bus_line = self.canvas.create_line(50, 530, 2000, 530, fill="lightgrey", width=5)
        self.canvas.create_text(60, 510, text="CAN Bus", fill="white", font=('Arial', 14, 'bold'))

        self.clock_label = self.canvas.create_text(
            100, 50, text=f"Clock = {self.clock}",
            fill="white",
            font=("Arial", 20, "bold"),
            tag="clock"
        )

        # add label next to clock label that tells if you press arrow keys (up/down) to increase/decrease speed
        self.canvas.create_text(
            150, 80, text="(Press UP/DOWN keys to adjust speed)",
            fill="white",
            font=("Arial", 12),
            tag="speed_label"
        )

        self.aux = True
        self.app.bind("<Up>", lambda e: self.increase_speed())
        self.app.bind("<Down>", lambda e: self.decrease_speed())
        self.app.bind("<space>", lambda e: self.small_clock())

        self.speed = 1000
        self.after_id = None 

        self.node_failure_active = False 

    def increase_speed(self):
        if self.speed < 2500:
            self.speed += 250
            print(f"{self.speed}")
            self.reschedule_clock()

    def decrease_speed(self):
        if self.node_failure_active == False:
            if self.speed > 250:
                self.speed -= 250
                print(f"{self.speed}")
                self.reschedule_clock()
        else:
            if self.speed > 250:
                self.speed -= 250
                print(f"{self.speed}")
                self.reschedule_clock()
            elif (self.speed <= 250) and (self.speed > 50):
                self.speed -= 50
                print(f"{self.speed}")
                self.reschedule_clock()
            elif self.speed == 50:
                self.speed = 10
                print(f"{self.speed}")
                self.reschedule_clock()

    def small_clock(self):
        if self.aux:
            self.speed = 1
            self.aux = False
        else:
            self.speed = 500
            self.aux = True
        self.reschedule_clock()

    def reschedule_clock(self):
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            print(f"Rescheduling clock with new speed: {self.speed} ms")
        if self.clock_running:
            self.after_id = self.after(self.speed, self.update_clock)

    def add_node(self, node_id=None, position=None, component_name=None):
        if len(self.nodes) >= self.max_nodes:
            CTkMessagebox(
                title="Maximum Nodes Reached",
                message="Cannot add more nodes. Maximum limit reached.",
                icon="warning"
            )
            return

        node_id = node_id or self.next_node_id
        x_position = 110 + len(self.nodes) * 150

        y_position = 410 if len(self.nodes) % 2 == 0 else 660
        position = (x_position, y_position)

        node = CANNode(node_id=node_id, bus=self.bus, node_comp=component_name)
        node.state = ERROR_ACTIVE
        node.mode = WAITING
        node.transmit_error_counter = 0
        node.receive_error_counter = 0

        self.nodes[node_id] = node
        self.node_positions[node_id] = position
        self.next_node_id += 1

        if component_name:
            self.assign_node_to_component(node_id, component_name)
        else:
            node.produced_ids = list(range(0, 2048))
            node.filters = list(range(0, 2048))

        self.bus.connect_node(node)
        self.draw_nodes()
        self.adjust_canvas_and_bus()

    def assign_node_to_component(self, node_id, component_name):
        if component_name not in COMPONENTS or node_id not in self.nodes:
            return

        comp_info = COMPONENTS[component_name]
        node = self.nodes[node_id]
        node.component = component_name

        start_id, end_id = comp_info["id_range"]
        node.produced_ids = list(range(start_id, end_id + 1))

        node.filters = []
        for listening_component in comp_info["listens_to"]:
            ls_start, ls_end = COMPONENTS[listening_component]["id_range"]
            node.filters.extend(range(ls_start, ls_end + 1))

    def adjust_canvas_and_bus(self):
        if self.node_positions:
            max_x_position = max(pos[0] for pos in self.node_positions.values()) + 200
        else:
            max_x_position = 2050

        self.canvas.configure(scrollregion=(0, 0, max_x_position, 1000))
        self.canvas.coords(self.bus_line, 50, 530, max_x_position, 530)

    def reset(self):
        for label in self.node_info_labels.values():
            self.canvas.delete(label)
        self.node_info_labels.clear()
        for visual_dict in self.node_visuals.values():
            for item in visual_dict.values():
                self.canvas.delete(item)
        self.node_visuals.clear()
        self.transmit_start_times.clear()
        self.draw_nodes()

    def draw_nodes(self):
        for visual_dict in self.node_visuals.values():
            for item in visual_dict.values():
                self.canvas.delete(item)
        self.node_visuals.clear()

        #self.node_info_labels.clear() #this line is not needed; it plays with the labels and ends up overwriting them with the initial value of the node_info_labels

        for label in self.node_info_labels.values():
            self.canvas.delete(label)
        self.node_info_labels.clear()

        for node_id, (x, y) in self.node_positions.items():
            node_width = 100
            node_height = 160
            top = y - node_height if y < 530 else y
            bottom = y if y < 530 else y + node_height

            node_rect = self.canvas.create_rectangle(
                x - node_width // 2, top,
                x + node_width // 2, bottom,
                outline="white", width=2
            )

            frame_rect = self.canvas.create_rectangle(
                x - node_width // 2 + 5, top + 10,
                x + node_width // 2 - 5, top + 60,
                fill="grey30", outline="white", width=1
            )
            self.canvas.create_text(
                x, top + 35, text="Frame", fill="white", font=("Arial", 12)
            )

            filter_rect = self.canvas.create_rectangle(
                x - node_width // 2 + 5, bottom - 60,
                x + node_width // 2 - 5, bottom - 10,
                fill="grey30", outline="white", width=1
            )
            self.canvas.create_text(
                x, bottom - 35, text="Filter", fill="white", font=("Arial", 12)
            )

            connection_line = self.canvas.create_line(
                x, bottom if y < 530 else top,
                x, 530, width=2, fill="grey"
            )

            self.node_visuals[node_id] = {
                "rect": node_rect,
                "frame": frame_rect,
                "filter": filter_rect,
                "line": connection_line,
            }

            node = self.nodes[node_id]
            component_name = getattr(node, "component", "None")
            info_text = (
                f"Component: {component_name}\n"
                f"State: {node.state}\n"
                f"Mode: {node.mode}\n"
                f"TEC: {node.transmit_error_counter}\n"
                f"REC: {node.receive_error_counter}"
            )

            # color = "lightgrey"
            # if node.state == BUS_OFF:
            #     color = "#590000"

            if node_id not in self.node_info_labels:
                info_label = self.canvas.create_text(
                    x,
                    top - 80 if y < 530 else bottom + 80,
                    text=info_text,
                    fill="lightgrey",
                    font=("Arial", 12),
                    justify="center"
                )
                self.node_info_labels[node_id] = info_label
            else:
                #self.canvas.delete(self.node_info_labels[node_id])
                self.canvas.itemconfig(self.node_info_labels[node_id], text=info_text)

            self.canvas.create_text(
                x,
                top - 20 if y < 530 else bottom + 20,
                text=f"Node {node_id}",
                fill="lightgrey",
                font=("Arial", 14, "bold")
            )

    def get_component_name(self, node_id):
        node = self.nodes.get(node_id)
        return getattr(node, "component", "None")

    def update_node_info(self, node_id):
        if node_id not in self.nodes or node_id not in self.node_info_labels:
            return

        node = self.nodes[node_id]
        comp_name = self.get_component_name(node_id)

        #delete old info text
        #self.canvas.delete(self.node_info_labels[node_id])

        info_text = (
            f"Component: {comp_name}\n"
            f"State: {node.state}\n"
            f"Mode: {node.mode}\n"
            f"TEC: {node.transmit_error_counter}\n"
            f"REC: {node.receive_error_counter}"
        )
        self.canvas.itemconfig(self.node_info_labels[node_id], text=info_text)

        visuals = self.node_visuals.get(node_id, {})
        frame_id = visuals.get("frame", None)
        filter_id = visuals.get("filter", None)

        msg = None
        cnt = 0
        idx = None
        for nd in self.nodes.keys():
            transmitting_node = self.nodes[nd]
            if transmitting_node.mode == TRANSMITTING and transmitting_node.message_queue:
                idx = self.nodes[nd].current_bit_index
                msg = self.nodes[nd].message_queue[0]
                cnt += 1
                break

        if node.state == BUS_OFF:
            if frame_id:
                self.canvas.itemconfig(frame_id, fill="#400000")
            if filter_id:
                self.canvas.itemconfig(filter_id, fill="#400000")
            return
        
        if node.mode == TRANSMITTING:
            if frame_id:
                print(cnt)
                if cnt > 1:
                    self.canvas.itemconfig(frame_id, fill="#f5c71a")
                else:
                    msg = node.message_queue[0]
                    self.canvas.itemconfig(frame_id, fill="green")
            if filter_id:
                self.canvas.itemconfig(filter_id, fill="grey30")
        elif node.mode == RECEIVING:
            if frame_id:
                self.canvas.itemconfig(frame_id, fill="grey30")
            if filter_id: 
                if isinstance(msg, OverloadFrame) or isinstance(msg, ErrorFrame):
                    self.canvas.itemconfig(filter_id, fill="green")
                else:
                    if cnt > 1:
                        self.canvas.itemconfig(filter_id, fill="yellow")
                    elif cnt == 1:
                        if idx <= msg.sections["rtr_start"]:
                            self.canvas.itemconfig(filter_id, fill="#f5c71a")
                        else:
                            if msg.identifier in node.filters:
                                self.canvas.itemconfig(filter_id, fill="green")
                            else:
                                self.canvas.itemconfig(filter_id, fill="red")
        else:
            if frame_id:
                self.canvas.itemconfig(frame_id, fill="grey30")
            if filter_id:
                self.canvas.itemconfig(filter_id, fill="grey30")

    def start_clock(self):
        if not self.clock_running:
            self.clock_running = True
            self.update_clock()

    def update_clock(self):
        current_clock = self.clock
        #maybe we have more msg at the same time
        while self.clock in self.schedule_times:
            node = random.choice(list(self.nodes.values()))
            data = [random.randint(0, 255) for _ in range(random.randint(0, 8))]
            msg = DataFrame(identifier=random.choice(node.produced_ids), sent_by=node.node_id, data=data)
            node.add_message_to_queue(msg)

            #remove first occurence of the clock
            self.schedule_times.remove(self.clock)
        if self.clock_running: 
            self.clock += 1
            self.display_clock()

            self.bus.simulate_step()

            self.refresh_nodes_and_log()
            self.update_bus_status()

            self.after_id = self.after(self.speed, self.update_clock)

    def display_clock(self):
        self.canvas.itemconfig(self.clock_label, text=f"Clock = {self.clock}")

    def refresh_nodes_and_log(self):
        for node_id in list(self.nodes.keys()):
            node = self.nodes[node_id]
            old_mode = self.canvas.itemcget(self.node_visuals[node_id]["frame"], "fill")  

            self.update_node_info(node_id)

            if node.mode == TRANSMITTING:
                if node_id not in self.transmit_start_times:
                    if node.message_queue:
                        msg = node.message_queue[0]
                        self.transmit_start_times[node_id] = (self.clock, msg.identifier)

            # If node just finished a message (meaning is_transmission_complete == True),
            # we log it with start_time..end_time
            if node.has_pending_message():
                msg = node.message_queue[0]
                if node.is_transmission_complete():
                    self.arbitration = ""
                    start_info = self.transmit_start_times.pop(node_id, None)
                    if start_info:
                        start_clock, msg_id = start_info
                        if msg.identifier:
                            self.app.log_panel.previous_logs.insert(0, f"Node {node_id} sent message of type {msg.frame_type} frame with ID {msg_id} from clock {start_clock} to clock {self.clock}.")
                        else: 
                            self.app.log_panel.previous_logs.insert(0, f"Node {node_id} sent message of type {msg.frame_type} frame from clock {start_clock} to clock {self.clock}.")

                        if isinstance(msg, DataFrame) or isinstance(msg, RemoteFrame):
                            if msg.error_type == None:
                                self.previous_frame = msg.unstuff_bitstream
                                self.previous_frame_type = msg.frame_type
                                self.previous_error_type = None
                                self.app.log_panel.add_log(f"Previous Frame: {self.previous_frame_type}; bitstream received by the nodes: {self.previous_frame}")
                            else: 
                                self.previous_frame = None
                                self.previous_frame_type = msg.frame_type
                                self.previous_error_type = msg.error_type
                                self.app.log_panel.add_log(f"Previous Frame: {self.previous_frame_type} frame was corrupted! Error {self.previous_error_type} detected by the nodes.")
                        else:
                            self.previous_frame = None
                            self.previous_frame_type = msg.frame_type
                            self.app.log_panel.add_log(f"Previous Frame: {self.previous_frame_type}")

                        #self.app.log_panel.add_log(f"Previous Frame: {msg.type_frame}; bitstream received by the nodes: {self.previous_frame}")
                    
                    node.message_queue.pop(0)
                    node.stop_transmitting()

    def update_bus_status(self):
        self.app.log_panel.clear_log()
        if self.bus.state == "Idle":
            self.app.log_panel.add_log("Bus: IDLE.")

        tx_nodes = [n for n in self.nodes.values() if n.mode == TRANSMITTING]
        if tx_nodes:
            for nd in tx_nodes:
                msg = nd.message_queue[0]
                if msg.identifier: 
                    self.app.log_panel.add_log(f"Transmitting: Node {nd.node_id} with message of type {msg.frame_type} frame with ID={msg.identifier}.\n")
                else:
                    self.app.log_panel.add_log(f"Transmitting: Node {nd.node_id} with message of type {msg.frame_type} frame.\n")
        else:
            self.app.log_panel.add_log("Transmitting: None\n")

        if self.bus.current_winner:
            self.arbitration = ""
            node = self.bus.current_winner
            msg = node.message_queue[0] if node.message_queue else None
            if msg:
                bs = msg.get_bitstream()
                idx = node.current_bit_index 
                partial = bs[:idx]

                #partial_str = "".join(str(b) for b in partial)
                
                field_str, str_manage = self.format_bitfields(msg, partial)
                self.app.log_panel.add_log("Bus: BUSY")
                
                self.app.log_panel.add_log(f"{str_manage}")
                self.app.log_panel.add_log(f"{field_str}")
                self.app.log_panel.add_log(f"\n")
                for log in self.app.log_panel.previous_logs:
                    self.app.log_panel.add_log(log)
        else: #more than one tranmsitting node; append the min bit sent by the transmitting nodes
            if len(tx_nodes) > 1:
                self.arbitration += f"{self.bus.current_bit}"
                self.app.log_panel.add_log(f"Bus: BUSY (in arbitration) \n{self.arbitration}")

        # if self.app.log_panel.previous_logs:
        #     self.app.log_panel.add_log(line for line in self.app.log_panel.previous_logs)

        if len(self.app.log_panel.previous_logs) > 0:
            for log in self.app.playground.previous_frame:
                self.app.log_panel.add_log(f"{log}")

    def format_bitfields(self, msg, partial_bits):
        if isinstance(msg, ErrorFrame):
            error_flag = partial_bits[:6]
            error_delimiter = partial_bits[6:14]

            def b2s(b): return "".join(str(x) for x in b)
            ef_str  = f"{b2s(error_flag):<6}\t{b2s(error_delimiter):<8}"
            sect_name = ""

            if len(partial_bits) < 7:
                sect_name = "Error Flag"
            else:
                sect_name = "Error Delimiter"

            return ef_str, f"(Transmitting {sect_name})"
        elif isinstance(msg, OverloadFrame):
            overload_flag = partial_bits[:6]
            overload_delimiter = partial_bits[6:14]

            def b2s(b): return "".join(str(x) for x in b)
            of_str = f"{b2s(overload_flag):<6}\t{b2s(overload_delimiter):<8}"
            sect_name = ""

            if len(partial_bits) < 7:
                sect_name = "Overload Flag"
            else:
                sect_name = "Overload Delimiter"

            return of_str, f"(Transmitting {sect_name})"
        elif isinstance(msg, RemoteFrame):
            sof = partial_bits[:1]
            id_end = msg.sections["rtr_start"]
            ctrl_end = msg.sections["control_start"]
            crc_start = msg.sections["crc_start"] 
            id_bits = partial_bits[1:id_end]
            rtr = partial_bits[id_end:(id_end+1)]
            ctrl = partial_bits[(id_end+1):crc_start]
            #doesnt send data
            crc_end = msg.sections["crc_end"]
            crc_delim_start = msg.get_ack_index() - 1
            crc_field = partial_bits[crc_start:crc_end]
            # print(crc_end)
            # print(f"{crc_delim_start}")
            crc_delimiter = partial_bits[crc_end:(crc_end+1)]
            ack_start = msg.get_ack_index()
            ack_field = partial_bits[(crc_end+1):(crc_end+2)]
            ack_delimiter = partial_bits[(crc_end+2):(crc_end+3)]
            eof = partial_bits[(crc_end+3):(crc_end+10)]
            intermission = partial_bits[(crc_end+10):]

            sect_name = ""
            transmitting_idx = len(partial_bits) - 1
            if transmitting_idx == 0:
                sect_name = "Start of Frame Bit" 
            elif transmitting_idx < id_end:
                sect_name = "Identifier Bits"
            elif transmitting_idx < id_end + 1:
                sect_name = "Remote Transmission Request Bit"
            elif transmitting_idx < crc_start:
                sect_name = "Control Field Bits"
            elif transmitting_idx < (crc_end):
                sect_name = "Cyclic Redundancy Check Bits"
            elif transmitting_idx < (crc_end+1):
                sect_name = "CRC Delimiter Bit"
            elif transmitting_idx < (crc_end+2):
                sect_name = "Acknowledgement Bit"
            elif transmitting_idx < (crc_end+3):
                sect_name = "Acknowledgement Delimiter Bit"
            elif transmitting_idx < (crc_end+10):
                sect_name = "End of Frame Bits"
            else:
                sect_name = "Intermission Bits"

            # print(f"sections: {msg.sections}")
            # print(f"{transmitting_idx}: {sect_name}")

            def b2s(b): return "".join(str(x) for x in b)
            rf_str = f"{b2s(sof)} {b2s(id_bits)} {b2s(rtr)} {b2s(ctrl)} {b2s(crc_field)} {b2s(crc_delimiter)} {b2s(ack_field)} {b2s(ack_delimiter)} {b2s(eof)}"

            receivers = [n for n in self.nodes.values() if n.mode == RECEIVING]
            receivers_str = ", ".join(str(n.node_id) for n in receivers) 
            str_manage = ""
            if sect_name == "Intermission Bits":
                str_manage = "(intermission)"
                rf_str += "(finished sending)"
            else: 
                str_manage = f"(Transmitting {sect_name})"
                if msg.get_ack_index() == len(partial_bits) - 1:
                    #give a little delay before sending the ack bit
                    time.sleep(1)
                    str_manage += f" Nodes {receivers_str} sent ACK bit."

            return rf_str, str_manage
        elif isinstance(msg, DataFrame) or msg.frame_type == "Data":
            sof = partial_bits[:1]
            id_end = msg.sections["rtr_start"]
            ctrl_end = msg.sections["control_start"]
            data_start = msg.sections["data_start"]
            data_end = msg.sections["crc_start"]
            id_bits = partial_bits[1:id_end]
            rtr = partial_bits[id_end:(id_end+1)]
            ctrl = partial_bits[(id_end+1):data_start]
            data = partial_bits[data_start:data_end]
            crc_end = msg.sections["crc_end"]
            crc_field = partial_bits[data_end:crc_end]
            crc_delimiter = partial_bits[crc_end:(crc_end+1)]
            ack_field = partial_bits[(crc_end+1):(crc_end+2)]
            ack_delimiter = partial_bits[(crc_end+2):(crc_end+3)]
            eof = partial_bits[(crc_end+3):(crc_end+10)]
            intermission = partial_bits[(crc_end+10):]

            sect_name = ""
            error_found = ""
            transmitting_idx = len(partial_bits) - 1
            if transmitting_idx == msg.error_bit_index:
                error_found = f"ERROR DETECTED: {msg.error_type} at bit {transmitting_idx}"
            if transmitting_idx == 0:
                sect_name = "Start of Frame Bit"
            elif transmitting_idx < id_end:
                sect_name = "Identifier Bits"
            elif transmitting_idx < id_end + 1:
                sect_name = "Remote Transmission Request Bit"
            elif transmitting_idx < ctrl_end:
                sect_name = "Control Field Bits"
            elif transmitting_idx < data_end:
                sect_name = "Data Field Bits"
            elif transmitting_idx < crc_end:
                sect_name = "Cyclic Redundancy Check Bits"
            elif transmitting_idx < (crc_end+1):
                sect_name = "CRC Delimiter Bit"
                msg.ack_slot = 0
            elif transmitting_idx < (crc_end+2):
                sect_name = "Acknowledgement Bit"
            elif transmitting_idx < (crc_end+3):
                sect_name = "Acknowledgement Delimiter Bit"
            elif transmitting_idx < (crc_end+10):
                sect_name = "End of Frame Bits"
            else:
                sect_name = "Intermission Bits"

            def b2s(b): return "".join(str(x) for x in b)
            df_str = f"{b2s(sof)} {b2s(id_bits)} {b2s(rtr)} {b2s(ctrl)} {b2s(data)} {b2s(crc_field)} {b2s(crc_delimiter)} {b2s(ack_field)} {b2s(ack_delimiter)} {b2s(eof)}"
            receivers = [n for n in self.nodes.values() if n.mode == RECEIVING]
            receivers_str = ", ".join(str(n.node_id) for n in receivers)
            str_manage = ""
            if sect_name == "Intermission Bits":
                str_manage = "(intermission)"
                df_str += "(finished sending)"
            else:
                str_manage = f"(Transmitting {sect_name})"
                if msg.get_ack_index() == len(partial_bits) - 1:
                    #give a little delay before sending the ack bit
                    time.sleep(1)
                    str_manage += f" Nodes {receivers_str} sent ACK bit."

            if error_found:
                str_manage = f"{error_found}"

            return df_str, str_manage
        else:
            return None

    def reset_clock(self):
        self.clock_running = False
        self.clock = 0
        self.display_clock()

class LogPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = ctk.CTkTextbox(self.log_frame, state="disabled", wrap="none", height=200)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)

        self.log_text.configure(font=("Roboto", 14))

        self.previous_logs = []

    def add_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

class PredefinedScenarios(ctk.CTkFrame):
    def __init__(self, master, playground, log_panel):
        super().__init__(master)
        self.master = master
        self.playground = playground
        self.log_panel = log_panel

        self.active_scenario = None
        self.run_active = False
        self.paused = True

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        title_frame = ctk.CTkFrame(self)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(title_frame, text="Predefined Scenarios in CAN", font=("Arial", 20, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame, text="Go to Interactive Simulation", command=self.master.show_interactive_simulation).pack(side="right", padx=10)

        self.left_column = ctk.CTkFrame(self)
        self.left_column.grid(row=1, column=0, sticky="ns", padx=10, pady=10)

        control_row = ctk.CTkFrame(self.left_column)
        control_row.pack(fill="x", pady=5)
        self.run_btn = ctk.CTkButton(control_row, text="Run", command=self.run_scenario)
        self.run_btn.pack(side="left", padx=5)
        self.pause_btn = ctk.CTkButton(control_row, text="Pause", command=self.pause_scenario)
        self.pause_btn.pack(side="left", padx=5)
        self.reset_btn = ctk.CTkButton(control_row, text="Reset", command=self.reset_scenario)
        self.reset_btn.pack(side="right", padx=5)

        self.initialize_scenario_menu(self.left_column)

        self.scenario_explanation = ctk.CTkLabel(
            self.left_column,
            text="Select a scenario to see its details",
            font=("Arial", 12), width=380, wraplength=380
        )
        self.scenario_explanation.pack(fill="x", pady=(10, 0))

        self.initialize_predefined_scenarios()

    def initialize_scenario_menu(self, parent):
        scenario_menu = ctk.CTkFrame(parent)
        scenario_menu.pack(fill="x", pady=10)

        self.frame_dropdown = ctk.CTkOptionMenu(
            scenario_menu,
            values=["Data Frame", "Remote Frame", "Error Frame", "Overload Frame"],
            command=self.select_frame
        )
        self.frame_dropdown.pack(fill="x", pady=5)
        self.frame_dropdown.set("Simple Message Transmission Test")

        self.error_dropdown = ctk.CTkOptionMenu(
            scenario_menu,
            values=["Bit Monitor Error", "Cyclic Redundancy Check Error",
                    "Bit Stuff Error", "Form Error", "Acknowledgment Error"],
            command=self.select_error
        )
        self.error_dropdown.pack(fill="x", pady=5)
        self.error_dropdown.set("Message Transmission with Error Test")

        self.arbitration_btn = ctk.CTkButton(
            scenario_menu, text="Arbitration Test",
            command=self.select_arbitration
        )
        self.arbitration_btn.pack(fill="x", pady=5)

        # self.node_failure_btn = ctk.CTkButton(
        #     scenario_menu, text="Node Failure Test",
        #     command=self.select_node_failure
        # )
        # self.node_failure_btn.pack(fill="x", pady=5)

    def initialize_predefined_scenarios(self):
        component_names = list(COMPONENTS.keys())
        for i in range(10):
            comp_name = component_names[i % len(component_names)]
            self.playground.add_node(component_name=comp_name)

    def select_frame(self, frame_type):
        self.active_scenario = "frame"
        explanations = {
            "Data Frame": "Demonstrates basic data transfer over CAN.",
            "Remote Frame": "Requests data from another node in CAN.",
            "Error Frame": "Demonstrates how error frames are broadcast if an error is detected.",
            "Overload Frame": "Indicates a node is overloaded and needs extra delay."
        }
        self.scenario_explanation.configure(
            text=f"{frame_type} - {explanations.get(frame_type, '')}"
        )

    def select_arbitration(self):
        self.active_scenario = "arbitration"
        self.scenario_explanation.configure(
            text="Arbitration Test: Multiple nodes attempt to send simultaneously."
        )

    def select_error(self, error_type):
        self.active_scenario = "error"
        explanations = {
            "Bit Monitor Error": "Occurs when the transmitter sees a different bit than it transmitted.",
            "Cyclic Redundancy Check Error": "Occurs when the CRC validation fails.",
            "Bit Stuff Error": "Occurs if more than 5 consecutive bits have the same level.",
            "Form Error": "Occurs when a fixed format field contains an illegal value.",
            "Acknowledgment Error": "Occurs when the transmitter doesn't get an ACK."
        }
        self.scenario_explanation.configure(
            text=f"{error_type} - {explanations.get(error_type, '')}"
        )

    def select_node_failure(self):
        self.active_scenario = "node_failure"
        self.scenario_explanation.configure(
            text="Node Failure Test: Tests transitions to error-passive or bus-off states."
        )

    def disable_other_scenarios(self, active_scenario):
        self.run_btn.configure(state="disabled")

    def run_scenario(self):
        if not self.active_scenario:
            self.log_panel.add_log("No scenario selected.")
            return
        
        self.run_active = True

        # 1) Basic frame transmissions
        if self.active_scenario == "frame":
            frame_type = self.frame_dropdown.get()
            if frame_type not in ["Data Frame", "Remote Frame", "Error Frame", "Overload Frame"]:
                self.log_panel.add_log("Please select a valid frame type.")
                return

            sender_node = self.select_node_dialog(f"Choose a node to transmit {frame_type}:")
            if not sender_node:
                return

            if frame_type == "Data Frame":
                data = [random.randint(0, 255) for _ in range(random.randint(1, 8))]
                msg = DataFrame(identifier=random.choice(sender_node.produced_ids), sent_by=sender_node.node_id, data=data)
                sender_node.add_message_to_queue(msg)
                # self.log_panel.add_log(
                #     f"[Scenario] Node {sender_node.node_id} queued DataFrame (ID={msg.identifier}) with data={data}."
                # )

            elif frame_type == "Remote Frame":
                msg = RemoteFrame(
                    identifier=random.choice(sender_node.produced_ids),
                    sent_by=sender_node.node_id
                )
                sender_node.add_message_to_queue(msg)
                # self.log_panel.add_log(
                #     f"[Scenario] Node {sender_node.node_id} queued RemoteFrame (ID={msg.identifier})."
                # )

            elif frame_type == "Error Frame":
                msg = ErrorFrame(sent_by=sender_node.node_id)
                sender_node.add_message_to_queue(msg)
                # self.log_panel.add_log(
                #     f"[Scenario] Node {sender_node.node_id} queued ErrorFrame."
                # )

            elif frame_type == "Overload Frame":
                msg = OverloadFrame(sent_by=sender_node.node_id)
                sender_node.add_message_to_queue(msg)
                # self.log_panel.add_log(
                #     f"[Scenario] Node {sender_node.node_id} queued OverloadFrame."
                # )

            self.run_active = True
            self.playground.start_clock()

        # 2) Arbitration
        elif self.active_scenario == "arbitration":
            #make the user select 2 or more nodes
            num_nodes = 0
            active_nodes = self.select_nodes_dialog("Choose nodes to send simultaneously:\n(comma-separated list of node IDs):")
            if len(active_nodes) < 2:
                self.log_panel.add_log("Not enough nodes for arbitration. Add more nodes first.")
                return

            msg_ids = [] 
            for node in active_nodes: 
                data = [random.randint(0, 255)] 
                #produce an id that is not the same as any other node msg queue; if 2 are the same, no node will win the arbitration
                msg_id = random.choice(node.produced_ids)
                while msg_id in msg_ids:
                    msg_id = random.choice(node.produced_ids)
                msg = DataFrame(identifier=msg_id, sent_by=node.node_id, data=data)
                node.add_message_to_queue(msg)
                self.log_panel.add_log(f"Node {node.node_id} queued DataFrame ID={msg.identifier} ({msg.identifier :011b}) for arbitration.")

            self.playground.start_clock()

        # 3) Errors
        elif self.active_scenario == "error":
            error_type = self.error_dropdown.get()
            node = self.select_node_dialog(f"Choose a node to send message with error {error_type}:")
            if not node:
                return
            self.playground.node_failure_active = True

            data = [random.randint(0, 255) for _ in range(random.randint(1, 8))]

            msg = CANMessage(identifier=random.choice(node.produced_ids), sent_by=node.node_id, data=data, frame_type="Data", error_type=error_type)
            print(f"bitstream: {msg.get_bitstream()}")
            print(f"Error type: {msg.error_type}")
            print(f"error index: {msg.error_bit_index}")
            print(f"msg bitstream: {msg.get_bitstream()}")
            node.add_message_to_queue(msg)

            # if not node.has_pending_message():
            #     self.log_panel.add_log(f"Node {node.node_id} has no pending message in queue.")
            #     return

            # msg = node.message_queue[-1]
            # if not hasattr(msg, "error_type"):
            #     self.log_panel.add_log(f"Message type {msg.frame_type} does not support error injection directly.")
            #     return

            error_mapping = {
                "Bit Monitor Error": "bit",
                "Cyclic Redundancy Check Error": "crc",
                "Bit Stuff Error": "stuff",
                "Form Error": "form",
                "Acknowledgment Error": "ack"
            }
            mapped_error = error_mapping.get(error_type)
            if mapped_error:
                getattr(msg, f"corrupt_{mapped_error}")()
                # print(
                #     f"[Scenario] Injected {error_type} into Node {node.node_id}'s message ID {msg.identifier}."
                # )
                print(f"error index: {msg.error_bit_index}")
            else:
                self.log_panel.add_log("Invalid or unsupported error type.")

            self.playground.start_clock()

        # 4) Node Failure test
        elif self.active_scenario == "node_failure":
            self.playground.node_failure_active = True
            self.frame_dropdown.set("Simple Message Transmission Test")
            node, error_type = self.select_node_and_error_type("Choose a node to forcibly fail")
            if (not node) or (not error_type):
                return
            #make the user select a type of error to inject
            node.state = ERROR_PASSIVE
            node.transmit_error_counter = 254
            self.playground.update_node_info(node.node_id)
            self.log_panel.add_log(
                f"[Scenario] Node {node.node_id} forced to ERROR_PASSIVE (TEC=254). "
                f"One more error might push it to BUS_OFF."
            )
            self.playground.start_clock()

        #disable all scenarios
        self.disable_other_scenarios(self.active_scenario)
        #disable run button
        self.run_btn.configure(state="disabled")


    def select_node_and_error_type(self, prompt):
        node = self.select_node_dialog("Choose a node to send message with error:")
        if not node:
            return None, None

        error_type = self.error_dropdown.get()
        if error_type not in ["Bit Monitor Error", "Cyclic Redundancy Check Error",
                              "Bit Stuff Error", "Form Error", "Acknowledgment Error"]:
            self.log_panel.add_log("Please select a valid error type.")
            return None, None

        return node, error_type

    def pause_scenario(self):
        if self.run_active:
            self.run_active = False
            self.playground.clock_running = False
            self.pause_btn.configure(text="Resume")
            self.log_panel.add_log("Scenario paused.")
        else:
            self.playground.clock_running = True
            self.run_active = True
            self.playground.update_clock()
            self.pause_btn.configure(text="Pause")

    def default_scenario_menu(self):
        #the select frame dropdown is set to the first option
        self.frame_dropdown.set("Simple Message Transmission Test")
        self.error_dropdown.set("Message Transmission with Error Test")

    def reset_scenario(self):
        self.run_active = False
        self.playground.node_failure_active = False
        self.playground.reset()
        self.playground.arbitration = ""
        self.default_scenario_menu()
        self.pause_btn.configure(text="Pause")
        self.run_btn.configure(state="normal")
        for node in list(self.playground.nodes.keys()):
            if self.playground.nodes[node].mode == TRANSMITTING:
                self.playground.nodes[node].stop_transmitting()
                self.playground.nodes[node].current_bit_index = 0
                self.playground.nodes[node].message_queue.clear()
            nid = self.playground.nodes[node]
            nid.reset_node()
            nid.mode = WAITING
            # for node in self.playground.nodes.keys():
            #     print(f"Node {node} mode: {self.playground.nodes[node].mode} and message queue: {self.playground.nodes[node].message_queue}")
            nid.current_bit_index = 0
            nid.message_queue.clear()
            self.playground.update_node_info(node)
        self.playground.bus.state = "Idle"
        self.playground.bus.reset_bus()
        self.playground.draw_nodes()
        self.log_panel.clear_log()
        self.active_scenario = None
        self.playground.reset_clock()
        self.playground.clock_running = False
        self.playground.previous_frame = None
        self.log_panel.previous_logs.clear()

    def select_node_dialog(self, prompt):
        if not self.playground.nodes:
            self.log_panel.add_log("No nodes available.")
            return None

        node_ids = list(self.playground.nodes.keys())
        dialog = ctk.CTkInputDialog(title="Select Node", text=f"Existing nodes: {node_ids}\n{prompt}")
        answer = dialog.get_input()
        if answer is None:
            return None
        try:
            node_id = int(answer)
        except ValueError:
            self.log_panel.add_log("Invalid node ID.")
            return None

        if node_id not in self.playground.nodes:
            self.log_panel.add_log(f"Node {node_id} does not exist.")
            return None

        return self.playground.nodes[node_id]
    
    def select_nodes_dialog(self, prompt):
        if not self.playground.nodes:
            self.log_panel.add_log("No nodes available.")
            return None
        
        node_ids = list(self.playground.nodes.keys())
        dialog = ctk.CTkInputDialog(title="Select Nodes", text=f"Existing nodes: {node_ids}\n{prompt}")
        answer = dialog.get_input() #returns a string of node ids separated by commas

        if answer is None:
            return None
        #split the string by commas
        node_ids = [int(node_id) for node_id in answer.split(",") if node_id.strip()]
        selected_nodes = []
        for node_id in node_ids:
            if node_id not in self.playground.nodes:
                #self.log_panel.add_log(f"Node {node_id} does not exist.")
                dialog = ctk.CTkInputDialog(title="Select Node", text=f"Node {node_id} does not exist. Try again.")
                #close the previous dialog
                dialog.destroy()
                return self.select_nodes_dialog(prompt)
            selected_nodes.append(self.playground.nodes[node_id])

        return selected_nodes
    
    def check_to_stop_scenario(self):
        for node in self.playground.nodes.values():
            if node.message_queue:
                return False
        return True

class InteractiveSimulation(ctk.CTkFrame):
    def __init__(self, master, playground, log_panel):
        super().__init__(master)
        self.master = master
        self.playground = playground
        self.log_panel = log_panel
        self.nodes = list(playground.nodes.values())
        self.bus = playground.bus
        self.message_load = MEDIUM
        self.paused = True
        self.run_active = False
        #self.error_interactive = False

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        title_frame = ctk.CTkFrame(self)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(title_frame, text="Interactive Simulation of CAN", 
                     font=("Arial", 20, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame, text="Go to Predefined Scenarios",
                      command=self.master.show_predefined_scenarios).pack(side="right", padx=10)

        left_column = ctk.CTkFrame(self)
        left_column.grid(row=1, column=0, sticky="ns", padx=10, pady=10)

        control_row = ctk.CTkFrame(left_column)
        control_row.pack(fill="x", pady=5)
        self.run_btn = ctk.CTkButton(control_row, text="Run", command=self.run_simulation)
        self.run_btn.pack(side="left", padx=5)
        self.pause_btn = ctk.CTkButton(control_row, text="Pause", command=self.pause_simulation)
        self.pause_btn.pack(side="left", padx=5)
        ctk.CTkButton(control_row, text="Reset", command=self.reset_simulation).pack(side="right", padx=5)

        interactive_menu = ctk.CTkFrame(left_column)
        interactive_menu.pack(fill="x", pady=10)
        ctk.CTkButton(interactive_menu, text="Edit Node Configuration",
                      command=self.edit_node_config).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Send Custom Message",
                      command=self.open_custom_message_window).pack(fill="x", pady=5)

        load_menu = ctk.CTkFrame(left_column)
        load_menu.pack(fill="x", pady=10)
        ctk.CTkLabel(load_menu, text="Message Load:").pack(anchor="w")
        self.load_dropdown = ctk.CTkOptionMenu(
            load_menu,
            values=[LOW.capitalize(), MEDIUM.capitalize(), HIGH.capitalize()],
            command=self.set_message_load
        )
        self.load_dropdown.set(MEDIUM.capitalize())
        self.load_dropdown.pack(fill="x", pady=5)

        self.nodes_queues = ctk.CTkFrame(left_column)
        self.nodes_queues.pack(fill="both", expand=True, pady=10)
        #for all nodes in self.playground nodes show the message queue

        #err = ctk.CTkCheckBox(self, text="Random Error Injection", variable=self.error_interactive, onvalue=1, offvalue=0)

    def open_custom_message_window(self):
        if not self.playground.nodes:
            self.log_panel.add_log("No nodes available to send messages.")
            return

        window = ctk.CTkToplevel(self)
        window.title("Send Custom Message")
        window.geometry("400x450")

        ctk.CTkLabel(window, text="Sender Node:").pack(pady=5)
        sender_var = ctk.StringVar(value="Select a Node")
        sender_menu = ctk.CTkOptionMenu(
            window, variable=sender_var,
            values=[f"Node {node_id}" for node_id in self.playground.nodes.keys()]
        )
        sender_menu.pack(pady=5)

        ctk.CTkLabel(window, text="Data (comma-separated bytes):").pack(pady=5)
        data_entry = ctk.CTkEntry(window)
        data_entry.pack(pady=5)

        ctk.CTkLabel(window, text="Error (optional):").pack(pady=5)
        error_var = ctk.StringVar(value="None")
        error_menu = ctk.CTkOptionMenu(
            window, variable=error_var,
            values=["None", "Bit Monitoring", "Bit Stuffing",
                    "Acknowledgment Error", "CRC Error", "Form Error"]
        )
        error_menu.pack(pady=5)

        def send_message():
            sender_selection = sender_var.get()
            if sender_selection == "Select a Node":
                self.log_panel.add_log("No sender node selected.")
                return

            try:
                sender_id = int(sender_selection.split()[1])
            except ValueError:
                self.log_panel.add_log("Invalid sender node ID.")
                return

            error_type = error_var.get()
            data_text = data_entry.get()
            try:
                data = [int(byte.strip()) for byte in data_text.split(",") if byte.strip()]
            except ValueError:
                self.log_panel.add_log("Invalid data. Enter comma-separated integers.")
                return
            
            if len(data) > 8:
                self.log_panel.add_log("Data length exceeds 8 bytes.")
                return

            sender_node = self.playground.nodes[sender_id]
            message = DataFrame(
                identifier=random.choice(sender_node.produced_ids),
                sent_by=sender_id,
                data=data
            )
            sender_node.add_message_to_queue(message)
            #self.log_panel.add_log(f"[Interactive] Node {sender_id} queued DataFrame ID={message.identifier} with data={data}")

            if error_type and error_type != "None":
                error_map = {
                    "Bit Monitoring": "bit",
                    "Bit Stuffing": "stuff",
                    "Acknowledgment Error": "ack",
                    "CRC Error": "crc",
                    "Form Error": "form"
                }
                mapped_err = error_map.get(error_type)
                if mapped_err:
                    getattr(message, f"corrupt_{mapped_err}")()
                    #self.log_panel.add_log(f"[Interactive] Injected {error_type} into message ID {message.identifier}.")

            window.destroy()
            self.playground.start_clock()

        ctk.CTkButton(window, text="Send", command=send_message).pack(pady=20)

    def set_message_load(self, load_level):
        self.message_load = load_level.lower()

    def run_simulation(self):
        self.run_active = True
        self.generate_messages()
        self.playground.start_clock()

    def pause_simulation(self):
        if self.run_active:
            self.run_active = False
            self.playground.clock_running = False
            self.pause_btn.configure(text="Resume")
            self.log_panel.add_log("Scenario paused.")
        else:
            self.playground.clock_running = True
            self.run_active = True
            self.playground.update_clock()
            self.pause_btn.configure(text="Pause")

    def reset_simulation(self):
        self.run_active = False
        self.playground.reset()
        self.pause_btn.configure(text="Pause")
        self.run_btn.configure(state="normal")
        for node in list(self.playground.nodes.keys()):
            if self.playground.nodes[node].mode == TRANSMITTING:
                self.playground.nodes[node].stop_transmitting()
                self.playground.nodes[node].current_bit_index = 0
                self.playground.nodes[node].message_queue.clear()
            nid = self.playground.nodes[node]
            nid.reset_node()
            nid.mode = WAITING
            # for node in self.playground.nodes.keys():
            #     print(f"Node {node} mode: {self.playground.nodes[node].mode} and message queue: {self.playground.nodes[node].message_queue}")
            nid.current_bit_index = 0
            nid.message_queue.clear()
            self.playground.update_node_info(node)
        self.playground.bus.state = "Idle"
        self.playground.bus.reset_bus()
        self.playground.draw_nodes()
        self.log_panel.clear_log()
        self.active_scenario = None
        self.playground.reset_clock()
        self.playground.clock_running = False
        self.playground.previous_frame = None
        self.log_panel.previous_logs.clear()

    def edit_node_config(self):
        window = ctk.CTkToplevel(self)
        window.title("Edit Node Configuration")
        window.geometry("400x400")

        ctk.CTkLabel(window, text="Select Node:").pack(pady=5)
        node_var = ctk.StringVar(value="Select a Node")
        node_dropdown = ctk.CTkOptionMenu(
            window, variable=node_var,
            values=[f"Node {nid}" for nid in self.playground.nodes.keys()] + ["Add New Node"]
        )
        node_dropdown.pack(pady=5)

        ctk.CTkLabel(window, text="Component:").pack(pady=5)
        component_var = ctk.StringVar(value="None")
        component_dropdown = ctk.CTkOptionMenu(
            window, variable=component_var,
            values=list(COMPONENTS.keys()) + ["None"]
        )
        component_dropdown.pack(pady=5)

        ctk.CTkLabel(window, text="Filters (comma-separated IDs):").pack(pady=5)
        filter_entry = ctk.CTkEntry(window)
        filter_entry.pack(pady=5)

        def add_new_node():
            comp_name = component_var.get() if component_var.get() in COMPONENTS else None
            self.playground.add_node(component_name=comp_name)
            node_dropdown.configure(
                values=[f"Node {nid}" for nid in self.playground.nodes.keys()] + ["Add New Node"]
            )
            self.log_panel.add_log("Added new node.")

        def delete_node():
            selection = node_var.get()
            if selection.startswith("Node "):
                node_id = int(selection.split()[1])
                if node_id in self.playground.nodes:
                    del self.playground.nodes[node_id]
                    del self.playground.node_positions[node_id]
                    if node_id in self.playground.node_visuals:
                        del self.playground.node_visuals[node_id]
                    if node_id in self.playground.node_info_labels:
                        del self.playground.node_info_labels[node_id]
                    self.playground.draw_nodes()
                    self.log_panel.add_log(f"Deleted Node {node_id}.")
                    window.destroy()
                else:
                    self.log_panel.add_log(f"Node {node_id} not found.")
            else:
                self.log_panel.add_log("No valid node selected to delete.")

        def save_changes():
            selection = node_var.get()
            if selection.startswith("Node "):
                node_id = int(selection.split()[1])
                if node_id in self.playground.nodes:
                    comp_name = component_var.get()
                    if comp_name in COMPONENTS:
                        self.playground.assign_node_to_component(node_id, comp_name)
                    else:
                        pass

                    filters_text = filter_entry.get()
                    if filters_text.strip():
                        try:
                            filters = [int(x.strip()) for x in filters_text.split(",")]
                            self.playground.nodes[node_id].filters = filters
                        except ValueError:
                            self.log_panel.add_log("Invalid filter list.")
                    self.playground.update_node_info(node_id)
                    self.log_panel.add_log(f"Saved changes for Node {node_id}.")
            elif selection == "Add New Node":
                add_new_node()

        ctk.CTkButton(window, text="Save Changes", command=save_changes).pack(pady=5)
        ctk.CTkButton(window, text="Delete Node", command=delete_node).pack(pady=5)
        ctk.CTkButton(window, text="Add New Node", command=add_new_node).pack(pady=5)

    def select_node_dialog(self, prompt):
        if not self.playground.nodes:
            self.log_panel.add_log("No nodes available.")
            return None

        node_ids = list(self.playground.nodes.keys())
        answer = ctk.CTkMessageBox(title="Select Node", text=f"Existing Nodes: {node_ids}")
        if not answer:
            return None
        try:
            node_id = int(answer)
        except ValueError:
            self.log_panel.add_log("Invalid node ID.")
            return None

        if node_id not in self.playground.nodes:
            self.log_panel.add_log(f"Node {node_id} does not exist.")
            return None
        return self.playground.nodes[node_id]

    def generate_messages(self):
        self.message_load = self.message_load.lower()
        self.playground.schedule_times = []
        if self.message_load == LOW:
            num_messages = int(len(self.playground.nodes) / 3)
        elif self.message_load == MEDIUM:
            num_messages = len(self.playground.nodes) 
        else:
            num_messages = len(self.playground.nodes) * 3

        #if the load changes, keep previous messages just add more like from that time t we have to send in fct of the load till t+100 the correspeonding nr of messages
        #but add to each node at diff clock cycle the messages
        t1 = self.playground.clock
        t2 = self.playground.clock + 99
        self.playground.schedule_times = [random.randint(t1, t2) for _ in range(num_messages)]

        print(f"{self.playground.schedule_times}")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    app = CANSimulatorApp()
    app.mainloop()
