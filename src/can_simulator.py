import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from tkinter import HORIZONTAL, simpledialog
import tkinter as tk
import random
import time

from can_bus import CANBus
from can_node import CANNode, TRANSMITTING, RECEIVING, WAITING, BUS_OFF, ERROR_PASSIVE, ERROR_ACTIVE
from can_message import DataFrame, RemoteFrame, ErrorFrame, OverloadFrame

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
        self.clear_scenario_frames()
        self.predefined_scenarios.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

    def show_interactive_simulation(self):
        self.clear_scenario_frames()
        self.interactive_simulation.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

    def clear_scenario_frames(self):
        self.predefined_scenarios.grid_remove()
        self.interactive_simulation.grid_remove()

class Playground(ctk.CTkFrame):
    """
    The Playground has:
     - canvas showing the CAN bus line
     - visualization of nodes (rectangles, lines, etc.)
     - clock-based simulation loop that calls bus.simulate_step()
    """
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

        self.clock_running = False
        self.clock = 0

        self.stuff_in = {}

        self.transmit_start_times = {}

        self.previous_frame = None

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
        self.node_visuals.clear()
        self.node_info_labels.clear()
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
                self.canvas.delete(self.node_info_labels[node_id])
                self.canvas.itemconfig(self.node_info_labels[node_id], text=info_text)

            # Node ID label
            self.canvas.create_text(
                x,
                top - 20 if y < 530 else bottom + 20,
                text=f"Node {node_id}",
                fill="lightgrey",
                font=("Arial", 14, "bold")
            )

    def get_component_name(self, node_id):
        """
        Helper to figure out which component name (if any) is assigned 
        to a particular node's ID range.
        """
        node = self.nodes.get(node_id)
        return getattr(node, "component", "None")

    def update_node_info(self, node_id):
        """
        Updates the textual info (state, mode, etc.) of a node on the canvas,
        as well as color for frame/filter rectangles to show TX or RX states.
        """
        if node_id not in self.nodes or node_id not in self.node_info_labels:
            return

        node = self.nodes[node_id]
        comp_name = self.get_component_name(node_id)

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
                cnt += 1
                msg = self.nodes[nd].message_queue[0]
                break

        if node.state == BUS_OFF:
            if frame_id:
                self.canvas.itemconfig(frame_id, fill="grey10")
            if filter_id:
                self.canvas.itemconfig(filter_id, fill="grey10")
            return
        
        if node.mode == TRANSMITTING:
            if frame_id:
                self.canvas.itemconfig(frame_id, fill="green")
            if filter_id:
                self.canvas.itemconfig(filter_id, fill="grey30")
        elif node.mode == RECEIVING:
            if frame_id:
                self.canvas.itemconfig(frame_id, fill="grey30")
            if filter_id:
                if cnt > 1:
                    self.canvas.itemconfig(filter_id, fill="yellow")
                elif cnt == 1:
                    if idx < 12:
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
        """
        Starts a simulation clock that regularly calls bus.simulate_step().
        """
        if not self.clock_running:
            self.clock_running = True
            self.update_clock()

    def update_clock(self):
        """
        Called repeatedly to increment the simulation time and
        drive the bus simulation.
        """
        if self.clock_running:
            self.clock += 1
            self.display_clock()

            # Let the bus do a single step of arbitration/transmission
            self.bus.simulate_step()

            # We check which nodes are transmitting, receiving, or waiting
            # and also see if a node just finished
            self.refresh_nodes_and_log()

            # Update bus status line
            self.update_bus_status()

            # Schedule next clock update
            self.after(1000, self.update_clock)

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
                            self.app.log_panel.add_log(
                                f"Node {node_id} sent message of type {msg.frame_type} frame with ID {msg_id} "
                                f"(decimal={msg_id}) from clock {start_clock} to clock {self.clock}."
                            )
                            self.app.log_panel.previous_logs.append(
                                f"Node {node_id} sent message of type {msg.frame_type} frame with ID {msg_id} "
                                f"(decimal={msg_id}) from clock {start_clock} to clock {self.clock}."
                            )
                        else: 
                            self.app.log_panel.add_log(
                                f"Node {node_id} sent message of type {msg.frame_type} frame "
                                f"from clock {start_clock} to clock {self.clock}."
                            )
                            self.app.log_panel.previous_logs.append(
                                f"Node {node_id} sent message of type {msg.frame_type} frame "
                                f"from clock {start_clock} to clock {self.clock}."
                            )

                        if isinstance(msg, DataFrame) or isinstance(msg, RemoteFrame):
                            self.previous_frame = msg.get_bitstream().unstuff_bitstream()

                        #self.app.log_panel.add_log(f"Previous {msg.frame_type} Frame recevied by nodes: {self.previous_frame}")
                    
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

        # 3) If there's a current_winner in bus, transmit normally
        if self.bus.current_winner:
            self.arbitration = ""
            node = self.bus.current_winner
            msg = node.message_queue[0] if node.message_queue else None
            if msg:
                bs = msg.get_bitstream()
                idx = node.current_bit_index 
                partial = bs[:idx]

                #partial_str = "".join(str(b) for b in partial)
                
                field_str, labels_str = self.format_bitfields(msg, partial)
                self.app.log_panel.add_log("Bus: BUSY")
                self.app.log_panel.add_log(f"{field_str}")
                self.app.log_panel.add_log(f"{labels_str}")
        else: #more than one tranmsitting node; append the min bit sent by the transmitting nodes
            if len(tx_nodes) > 1:
                self.arbitration += f"{self.bus.current_bit}"
                self.app.log_panel.add_log(f"Bus: BUSY (in arbitration) \n{self.arbitration}")

        # if self.app.log_panel.previous_logs:
        #     self.app.log_panel.add_log(line for line in self.app.log_panel.previous_logs)

        if self.app.playground.previous_frame:
            self.app.log_panel.add_log(f"Previous Frame: {self.app.playground.previous_frame}")

    def format_bitfields(self, msg, partial_bits):
        if isinstance(msg, ErrorFrame):
            error_flag = partial_bits[:6]
            error_delimiter = partial_bits[6:14]

            def b2s(b): return "".join(str(x) for x in b)
            ef_str  = f"{b2s(error_flag):<6}\t{b2s(error_delimiter):<8}"
            ef_label= f"{'(ERRORFLAG)':<6}\t{'(DELIM)':<8}"

            return ef_str, ef_label
        elif isinstance(msg, OverloadFrame):
            overload_flag = partial_bits[:6]
            overload_delimiter = partial_bits[6:14]

            def b2s(b): return "".join(str(x) for x in b)
            of_str = f"{b2s(overload_flag):<6}\t{b2s(overload_delimiter):<8}"
            of_label = f"{'(OVERLOADFLAG)':<6}\t{'(DELIM)':<8}"

            return of_str, of_label
        elif isinstance(msg, RemoteFrame):
            sof = partial_bits[:1]
            id_bits = partial_bits[1:12]
            rtr = partial_bits[12:13]
            ctrl = partial_bits[13:19]
            #doesnt send data
            crc_field = partial_bits[19:34]
            crc_delimiter = partial_bits[34:35]
            ack_field = partial_bits[35:36]
            ack_delimiter = partial_bits[36:37]
            eof = partial_bits[37:44]
            intermission = partial_bits[44:]

            def b2s(b): return "".join(str(x) for x in b)
            rf_str = f"{b2s(sof):<1}\t{b2s(id_bits):<11}\t{b2s(rtr):<1}\t{b2s(ctrl):<6}\t{b2s(crc_field):<15}\t{b2s(crc_delimiter):<1}\t{b2s(ack_field):<1}\t{b2s(ack_delimiter):<1}\t{b2s(eof):<7}"
            rf_label = f"{'(SOF)':<1}\t{'(ID)':<11}\t{'(RTR)':<1}\t{'(CTRL)':<6}\t{'(CRC)':<15}\t{'(DELIM)':<1}\t{'(ACK)':<1}\t{'(DELIM)':<1}\t{'(EOF)':<7}"

            return rf_str, rf_label
        elif isinstance(msg, DataFrame):
            data_start = 19
            data_end = 8 * len(msg.data_field) + data_start
            sof = partial_bits[:1]
            id_bits = partial_bits[1:12]
            rtr = partial_bits[12:13]
            ctrl = partial_bits[13:19]
            data = partial_bits[data_start:data_end]
            crc_field = partial_bits[data_end:(data_end + 15)]
            crc_delimiter = partial_bits[(data_end + 15):(data_end + 16)]
            ack_field = partial_bits[(data_end + 16):(data_end + 17)]
            ack_delimiter = partial_bits[(data_end + 17):(data_end + 18)]
            eof = partial_bits[(data_end + 18):(data_end + 25)]
            intermission = partial_bits[(data_end + 25):]    

            data_tabs = "\t" * (len(msg.data_field) - 1)

            def b2s(b): return "".join(str(x) for x in b)
            data_str = b2s(data)
            max_data_len = 64
            if len(data_str) > max_data_len:
                data_str = data_str[:max_data_len] 
            data_bits_len = int(data_end - data_start)
            df_str = f"{b2s(sof):<1}\t{b2s(id_bits):<11}\t\t{b2s(rtr):<1}\t{b2s(ctrl):<6}\t{data_str}\t{b2s(crc_field):<15}\t{b2s(crc_delimiter):<1}\t{b2s(ack_field):<1}\t{b2s(ack_delimiter):<1}\t{b2s(eof):<7}"
            df_label = f"{'(SOF)':<1}\t{'(ID)':<11}\t\t{'(RTR)':<1}\t{'(CTRL)':<6}\t{'(DATA)':<64}{data_tabs}{'(CRC)':<15}\t\t{'(DELIM)':<1}\t{'(ACK)':<1}\t{'(DELIM)':<1}\t{'(EOF)':<7}"

            return df_str, df_label
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

        self.log_text = ctk.CTkTextbox(self.log_frame, state="disabled", wrap="word", height=200)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)

        self.log_text.configure(font=("Courier New", 12))

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
    """
    A set of buttons to run pre-packaged scenarios:
      - Basic Data/Remote/Error Frame transmissions
      - Arbitration test
      - Error injection
      - Node failure transitions
    """
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

        # Title + Navigation
        title_frame = ctk.CTkFrame(self)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(title_frame, text="Predefined Scenarios in CAN",
                     font=("Arial", 20, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame, text="Go to Interactive Simulation",
                      command=self.master.show_interactive_simulation).pack(side="right", padx=10)

        # Left Column for scenario controls
        left_column = ctk.CTkFrame(self)
        left_column.grid(row=1, column=0, sticky="ns", padx=10, pady=10)

        # Control row: Run, Pause, Reset
        control_row = ctk.CTkFrame(left_column)
        control_row.pack(fill="x", pady=5)
        ctk.CTkButton(control_row, text="Run", command=self.run_scenario).pack(side="left", padx=5)
        self.pause_btn = ctk.CTkButton(control_row, text="Pause", command=self.pause_scenario)
        self.pause_btn.pack(side="left", padx=5)
        ctk.CTkButton(control_row, text="Reset", command=self.reset_scenario).pack(side="right", padx=5)

        # Scenario selection
        self.initialize_scenario_menu(left_column)

        # Explanation label
        self.scenario_explanation = ctk.CTkLabel(
            left_column,
            text="Select a scenario to see its details",
            font=("Arial", 12), width=380, wraplength=380
        )
        self.scenario_explanation.pack(fill="x", pady=(10, 0))

        # Auto-populate a few nodes for demonstration
        self.initialize_predefined_scenarios()

    def initialize_scenario_menu(self, parent):
        scenario_menu = ctk.CTkFrame(parent)
        scenario_menu.pack(fill="x", pady=10)

        # Frame Type Dropdown
        self.frame_dropdown = ctk.CTkOptionMenu(
            scenario_menu,
            values=["Data Frame", "Remote Frame", "Error Frame", "Overload Frame"],
            command=self.select_frame
        )
        self.frame_dropdown.pack(fill="x", pady=5)
        self.frame_dropdown.set("Simple Message Transmission Test")

        # Error Dropdown
        self.error_dropdown = ctk.CTkOptionMenu(
            scenario_menu,
            values=["Bit Monitor Error", "Cyclic Redundancy Check Error",
                    "Bit Stuff Error", "Form Error", "Acknowledgment Error"],
            command=self.select_error
        )
        self.error_dropdown.pack(fill="x", pady=5)
        self.error_dropdown.set("Message Transmission with Error Test")

        # Arbitration Test
        self.arbitration_btn = ctk.CTkButton(
            scenario_menu, text="Arbitration Test",
            command=self.select_arbitration
        )
        self.arbitration_btn.pack(fill="x", pady=5)

        # Node Failure Test
        self.node_failure_btn = ctk.CTkButton(
            scenario_menu, text="Node Failure Test",
            command=self.select_node_failure
        )
        self.node_failure_btn.pack(fill="x", pady=5)

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
        pass

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

            # Let the user pick a node for the "sender"
            sender_node = self.select_node_dialog(f"Choose a node to transmit {frame_type}:")
            if not sender_node:
                return

            if frame_type == "Data Frame":
                data = [random.randint(0, 255) for _ in range(random.randint(1, 8))]
                msg = DataFrame(
                    identifier=random.choice(sender_node.produced_ids),
                    sent_by=sender_node.node_id,
                    data=data
                )
                sender_node.add_message_to_queue(msg)
                self.log_panel.add_log(
                    f"[Scenario] Node {sender_node.node_id} queued DataFrame (ID={msg.identifier}) with data={data}."
                )

            elif frame_type == "Remote Frame":
                msg = RemoteFrame(
                    identifier=random.choice(sender_node.produced_ids),
                    sent_by=sender_node.node_id
                )
                sender_node.add_message_to_queue(msg)
                self.log_panel.add_log(
                    f"[Scenario] Node {sender_node.node_id} queued RemoteFrame (ID={msg.identifier})."
                )

            elif frame_type == "Error Frame":
                msg = ErrorFrame(sent_by=sender_node.node_id)
                sender_node.add_message_to_queue(msg)
                self.log_panel.add_log(
                    f"[Scenario] Node {sender_node.node_id} queued ErrorFrame."
                )

            elif frame_type == "Overload Frame":
                msg = OverloadFrame(sent_by=sender_node.node_id)
                sender_node.add_message_to_queue(msg)
                self.log_panel.add_log(
                    f"[Scenario] Node {sender_node.node_id} queued OverloadFrame."
                )

            self.run_active = True
            self.playground.start_clock()
            self.disable_other_scenarios(self.active_scenario)

        # 2) Arbitration
        elif self.active_scenario == "arbitration":
            self.log_panel.add_log("Starting Arbitration Test. Multiple nodes will try to send.")
            active_nodes = list(self.playground.nodes.values())
            if len(active_nodes) < 2:
                self.log_panel.add_log("Not enough nodes for arbitration. Add more nodes first.")
                return

            for node in active_nodes: 
                data = [random.randint(0, 255)] 
                msg = DataFrame(identifier=random.choice(node.produced_ids),
                                sent_by=node.node_id,
                                data=data)
                node.add_message_to_queue(msg)
                self.log_panel.add_log(f"Node {node.node_id} queued DataFrame ID={msg.identifier} for arbitration.")

            self.playground.start_clock()

        # 3) Errors
        elif self.active_scenario == "error":
            error_type = self.error_dropdown.get()
            node = self.select_node_dialog(f"Choose a node to inject {error_type} into:")
            if not node:
                return

            if not node.has_pending_message():
                self.log_panel.add_log(f"Node {node.node_id} has no pending message in queue.")
                return

            msg = node.message_queue[-1]
            if not hasattr(msg, "error_type"):
                self.log_panel.add_log(f"Message type {msg.frame_type} does not support error injection directly.")
                return

            error_mapping = {
                "Bit Monitor Error": "bit_error",
                "Cyclic Redundancy Check Error": "crc_error",
                "Bit Stuff Error": "stuff_error",
                "Form Error": "form_error",
                "Acknowledgment Error": "ack_error"
            }
            mapped_error = error_mapping.get(error_type)
            if mapped_error:
                getattr(msg, f"corrupt_{mapped_error}")()
                self.log_panel.add_log(
                    f"[Scenario] Injected {error_type} into Node {node.node_id}'s message ID {msg.identifier}."
                )
            else:
                self.log_panel.add_log("Invalid or unsupported error type.")

            self.playground.start_clock()

        # 4) Node Failure test
        elif self.active_scenario == "node_failure":
            node = self.select_node_dialog("Choose a node to forcibly fail:")
            if not node:
                return
            node.state = ERROR_PASSIVE
            node.transmit_error_counter = 254
            self.playground.update_node_info(node.node_id)
            self.log_panel.add_log(
                f"[Scenario] Node {node.node_id} forced to ERROR_PASSIVE (TEC=254). "
                f"One more error might push it to BUS_OFF."
            )
            self.playground.start_clock()

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

    def reset_scenario(self):
        self.run_active = False
        self.playground.reset()
        self.playground.arbitration = ""
        for node in list(self.playground.nodes.keys()):
            if self.playground.nodes[node].mode == TRANSMITTING:
                self.playground.nodes[node].stop_transmitting()
                self.playground.nodes[node].current_bit_index = 0
                self.playground.nodes[node].message_queue.clear()
            nid = self.playground.nodes[node]
            nid.reset_node()
            nid.mode = WAITING
            for node in self.playground.nodes.keys():
                print(f"Node {node} mode: {self.playground.nodes[node].mode} and message queue: {self.playground.nodes[node].message_queue}")
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
        """
        Let the user pick a node ID from the existing nodes via a simple
        text-based dialog. Return the corresponding CANNode or None.
        """
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


class InteractiveSimulation(ctk.CTkFrame):
    """
    Allows the user to run a continuous simulation where nodes periodically
    send messages based on a chosen load, and the user can inject errors or 
    send custom frames on the fly.
    """
    def __init__(self, master, playground, log_panel):
        super().__init__(master)
        self.master = master
        self.playground = playground
        self.log_panel = log_panel
        self.nodes = list(playground.nodes.values())
        self.bus = playground.bus
        self.message_load = MEDIUM
        self.paused = True
        #self.error_interactive = False

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        # Title + Navigation
        title_frame = ctk.CTkFrame(self)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(title_frame, text="Interactive Simulation of CAN", 
                     font=("Arial", 20, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame, text="Go to Predefined Scenarios",
                      command=self.master.show_predefined_scenarios).pack(side="right", padx=10)

        # Left Column for controls
        left_column = ctk.CTkFrame(self)
        left_column.grid(row=1, column=0, sticky="ns", padx=10, pady=10)

        # Control row
        control_row = ctk.CTkFrame(left_column)
        control_row.pack(fill="x", pady=5)
        ctk.CTkButton(control_row, text="Run", command=self.run_simulation).pack(side="left", padx=5)
        ctk.CTkButton(control_row, text="Pause", command=self.pause_simulation).pack(side="left", padx=5)
        ctk.CTkButton(control_row, text="Reset", command=self.reset_simulation).pack(side="right", padx=5)

        # Some config & message injection
        interactive_menu = ctk.CTkFrame(left_column)
        interactive_menu.pack(fill="x", pady=10)
        ctk.CTkButton(interactive_menu, text="Edit Node Configuration",
                      command=self.edit_node_config).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Send Custom Message",
                      command=self.open_custom_message_window).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Inject Errors",
                      command=self.inject_errors).pack(fill="x", pady=5)

        # Load selection
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

        #err = ctk.CTkCheckBox(self, text="Random Error Injection", variable=self.error_interactive, onvalue=1, offvalue=0)

    def open_custom_message_window(self):
        """
        Let user choose a sender node, data, and optional error injection.
        """
        if not self.playground.nodes:
            self.log_panel.add_log("No nodes available to send messages.")
            return

        window = ctk.CTkToplevel(self)
        window.title("Send Custom Message")
        window.geometry("400x450")

        # Sender
        ctk.CTkLabel(window, text="Sender Node:").pack(pady=5)
        sender_var = ctk.StringVar(value="Select a Node")
        sender_menu = ctk.CTkOptionMenu(
            window, variable=sender_var,
            values=[f"Node {node_id}" for node_id in self.playground.nodes.keys()]
        )
        sender_menu.pack(pady=5)

        # Data Entry
        ctk.CTkLabel(window, text="Data (comma-separated bytes):").pack(pady=5)
        data_entry = ctk.CTkEntry(window)
        data_entry.pack(pady=5)

        # Error Injection
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

            sender_node = self.playground.nodes[sender_id]
            message = DataFrame(
                identifier=random.choice(sender_node.produced_ids),
                sent_by=sender_id,
                data=data
            )
            sender_node.add_message_to_queue(message)
            self.log_panel.add_log(f"[Interactive] Node {sender_id} queued DataFrame ID={message.identifier} with data={data}")

            if error_type and error_type != "None":
                error_map = {
                    "Bit Monitoring": "bit_error",
                    "Bit Stuffing": "stuff_error",
                    "Acknowledgment Error": "ack_error",
                    "CRC Error": "crc_error",
                    "Form Error": "form_error"
                }
                mapped_err = error_map.get(error_type)
                if mapped_err:
                    getattr(message, f"corrupt_{mapped_err}")()
                    self.log_panel.add_log(f"[Interactive] Injected {error_type} into message ID {message.identifier}.")

            window.destroy()
            self.playground.start_clock()

        ctk.CTkButton(window, text="Send", command=send_message).pack(pady=20)

    def set_message_load(self, load_level):
        self.message_load = load_level.lower()

    def run_simulation(self):
        self.playground.start_clock()

    def pause_simulation(self):
        self.paused = True
        self.playground.clock_running = False

    def reset_simulation(self):
        self.playground.reset()
        self.log_panel.clear_log()
        self.playground.reset_clock()
        self.log_panel.previous_logs.clear()

    def edit_node_config(self):
        """
        Basic placeholder for modifying node filters, or adding/deleting nodes.
        """
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

    def inject_errors(self):
        node = self.select_node_dialog("Select a node to inject error into:")
        if not node:
            return
        if not node.has_pending_message():
            self.log_panel.add_log("Node has no pending messages in queue.")
            return

        msg = node.message_queue[-1]
        error_type = random.choice(["bit_error", "stuff_error", "crc_error", "ack_error", "form_error"])
        getattr(msg, f"corrupt_{error_type}")()
        self.log_panel.add_log(
            f"[Interactive] Injected {error_type} into Node {node.node_id}'s message ID {msg.identifier}."
        )

        self.playground.start_clock()

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


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    app = CANSimulatorApp()
    app.mainloop()
