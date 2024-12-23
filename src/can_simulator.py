import customtkinter as ctk
from tkinter import HORIZONTAL
from can_bus import CANBus
from can_node import CANNode, TRANSMITTING, RECEIVING, WAITING, BUS_OFF, ERROR_PASSIVE, ERROR_ACTIVE
from can_message import CANMessage, DataFrame, RemoteFrame, ErrorFrame, OverloadFrame
import time
import random

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

COMPONENTS = {
    "Control Unit": {"id_range": (0, 511), "listens_to": ["Control Unit", "Sensors", "Actuators"]},
    "Power Supply Unit": {"id_range": (512, 1023), "listens_to": ["Control Unit","Power Supply Unit", "Sensors"]},
    "Sensors": {"id_range": (1024, 1535), "listens_to": ["Control Unit","Sensors", "Actuators"]},
    "Actuators": {"id_range": (1536, 2047), "listens_to": ["Control Unit", "Sensors"]}
}

class CANSimulatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CAN Simulator Project")
        self.geometry("1200x800")

        self.playground = Playground(self, self)
        self.predefined_scenarios = PredefinedScenarios(self, self.playground)
        self.interactive_simulation = InteractiveSimulation(self, self.playground)

        self.message_queue = [] 
        self.show_predefined_scenarios()

    def show_predefined_scenarios(self):
        self.clear_frames()
        self.predefined_scenarios.pack(expand=True, fill="both")

    def show_interactive_simulation(self):
        self.clear_frames()
        self.interactive_simulation.pack(expand=True, fill="both")

    def clear_frames(self):
        for widget in self.winfo_children():
            widget.pack_forget()

    def add_to_message_queue(self, message):
        self.message_queue.append(message)

    def remove_from_message_queue(self, message):
        self.message_queue.remove(message)

    def get_message_queue(self):
        return self.message_queue

class Playground(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.bus = CANBus()
        self.components = {}
        self.nodes = {}
        self.node_positions = {}
        self.node_visuals = {}
        self.node_info_labels = {}
        self.next_node_id = 1
        self.max_nodes = 50
        self.show_states = True
        self.clock_running = False
        self.clock_label = None
        self.clock = 0
        self.total_id_ranges = 2048

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(self, bg="black", scrollregion=(0, 0, 2000, 1000))
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.scroll_x = ctk.CTkScrollbar(self, orientation=HORIZONTAL, command=self.canvas.xview)
        self.scroll_x.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10)) 

        self.canvas.configure(xscrollcommand=self.scroll_x.set)

        self.bus_line = self.canvas.create_line(50, 530, 2000, 530, fill="lightgrey", width=5)
        self.canvas.create_text(60, 510, text="CAN Bus", fill="white", font=('Arial', 14, 'bold'))
        self.clock_label = self.canvas.create_text(100, 50, text = f"Clock = {self.clock}", fill="white", font=("Arial", 20, "bold"), tag="clock")

    def add_node(self, node_id=None, position=None, component_name=None):
        if len(self.nodes) >= self.max_nodes:
            return

        node_id = node_id or self.next_node_id
        x_position = 110 + len(self.nodes) * 150
        y_position = 410 if len(self.nodes) % 2 == 0 else 660  
        position = (x_position, y_position)

        node = CANNode(node_id, self.bus)
        node.state = "Error Active"
        node.mode = "Waiting"
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

        self.draw_nodes()
        self.adjust_canvas_and_bus()

    def adjust_canvas_and_bus(self):
        if self.node_positions:
            max_x_position = max(pos[0] for pos in self.node_positions.values()) + 200
        else:
            max_x_position = 2050 

        self.canvas.configure(scrollregion=(0, 0, max_x_position, 1000))

        self.canvas.coords(self.bus_line, 50, 530, max_x_position, 530)

    def assign_node_to_component(self, node_id, component_name):
        if component_name not in COMPONENTS or node_id not in self.nodes:
            return
        
        component = COMPONENTS[component_name]
        node = self.nodes[node_id]

        node.produced_ids = list(range(component["id_range"][0], component["id_range"][1] + 1))

        node.filters = []
        for listening_component in component["listens_to"]:
            listening_ids = range(COMPONENTS[listening_component]["id_range"][0], COMPONENTS[listening_component]["id_range"][1] + 1)
            node.filters.extend(listening_ids)

    def reset(self):
        self.nodes.clear()
        self.node_positions.clear()
        self.node_visuals.clear()
        self.bus = CANBus()
        self.draw_nodes()

    def draw_nodes(self):
        for visual in self.node_visuals.values():
            for item in visual.values():
                self.canvas.delete(item)
        self.node_visuals.clear()

        for node_id, (x, y) in self.node_positions.items():
            node_width = 100
            node_height = 160
            top = y - node_height if y < 530 else y
            bottom = y if y < 530 else y + node_height

            node_rect = self.canvas.create_rectangle(
                x - node_width // 2, top, x + node_width // 2, bottom, outline="white", width=2
            )

            frame_rect = self.canvas.create_rectangle(
                x - node_width // 2 + 5, top + 10, x + node_width // 2 - 5, top + 60, fill="grey30", outline="white", width=1
            )
            self.canvas.create_text(
                x, top + 35, text="Frame", fill="white", font=("Arial", 12)
            )

            filter_rect = self.canvas.create_rectangle(
                x - node_width // 2 + 5, bottom - 60, x + node_width // 2 - 5, bottom - 10, fill="grey30", outline="white", width=1
            )
            self.canvas.create_text(
                x, bottom - 35, text="Filter", fill="white", font=("Arial", 12)
            )

            connection_line = self.canvas.create_line(
                x, bottom if y < 530 else top, x, 530, width=2, fill="grey"
            )

            self.node_visuals[node_id] = {
                "rect": node_rect,
                "frame": frame_rect,
                "filter": filter_rect,
                "line": connection_line,
            }

            node = self.nodes[node_id]
            info_text = f"State: {node.state}\nMode: {node.mode}\nTEC: {node.transmit_error_counter}\nREC: {node.receive_error_counter}"
            info_label = self.canvas.create_text(x, top - 80 if y < 580 else bottom + 80, text=info_text, fill="lightgrey", font=("Arial", 15))
            self.node_info_labels[node_id] = info_label

            self.canvas.create_text(
                x, top - 20 if y < 530 else bottom + 20, text=f"Node {node_id}", fill="lightgrey", font=("Arial", 14, "bold")
            )

    def update_node_state(self, node_id, transmitting=False, filtering=False):
        if node_id not in self.node_visuals:
            return

        frame_color = "green" if transmitting else "grey30"
        filter_color = "red" if filtering else "grey30"

        self.canvas.itemconfig(self.node_visuals[node_id]["frame"], fill=frame_color)
        self.canvas.itemconfig(self.node_visuals[node_id]["filter"], fill=filter_color)

    def update_node_info(self, node_id, state=None, mode=None, tec=None, rec=None):
        if node_id not in self.nodes or node_id not in self.node_info_labels:
            return

        node = self.nodes[node_id]
        if state is not None:
            node.state = state
        if mode is not None:
            node.mode = mode
        if tec is not None:
            node.tec = tec
        if rec is not None:
            node.rec = rec

        info_text = f"State: {node.state}\nMode: {node.mode}\nTEC: {node.transmit_error_counter}\nREC: {node.receive_error_counter}"
        self.canvas.itemconfig(self.node_info_labels[node_id], text=info_text)

    def animate_message_transmission(self, sender, receivers, message):
        sender_pos = self.node_positions[sender.node_id]
        message_visual = self.canvas.create_oval(
            sender_pos[0] - 10, sender_pos[1] - 10, sender_pos[0] + 10, sender_pos[1] + 10,
            fill="blue", outline=""
        )

        def to_bus(step=0):
            bus_pos = (sender_pos[0], 530) 
            dx = (bus_pos[0] - sender_pos[0]) / 20
            dy = (bus_pos[1] - sender_pos[1]) / 20
            self.canvas.move(message_visual, dx, dy)

            if step < 20:
                self.canvas.after(50, lambda: to_bus(step + 1))
            else:
                self.glow_bus_line(True)
                transmit_to_receivers()

        def transmit_to_receivers():
            def to_receiver(receiver, step=0):
                receiver_pos = self.node_positions[receiver.node_id]
                dx = (receiver_pos[0] - sender_pos[0]) / 20
                dy = (receiver_pos[1] - 530) / 20
                self.canvas.move(message_visual, dx, dy)
                if step < 20:
                    self.canvas.after(50, lambda: to_receiver(receiver, step + 1))
                else:
                    self.glow_node(receiver.node_id, transmitting=False)

            for receiver in receivers:
                self.glow_node(receiver.node_id, transmitting=True)
                self.canvas.after(200, lambda: to_receiver(receiver))

            self.canvas.after(1000, lambda: self.clear_animation(message_visual))
            self.canvas.after(1000, lambda: self.glow_bus_line(False))

        to_bus()

    def glow_bus_line(self, active=True):
        color = "yellow" if active else "lightgrey"
        self.canvas.itemconfig(self.bus_line, fill=color)

    def glow_node(self, node_id, transmitting=False, receiving=False):
        if node_id not in self.node_visuals:
            return

        if transmitting:
            color = "green"
        elif receiving:
            color = "red"
        else:
            color = "grey30"

        self.canvas.itemconfig(self.node_visuals[node_id]["frame"], fill=color)

    def clear_animation(self, visual):
        self.canvas.delete(visual)

    def process_bits(self, sender, message):
        bitstream = message.get_bitstream()  # Get the bitstream of the message
        receivers = [node for node in self.nodes.values() if node != sender]
        arbitration_lost = False

        def transmit_bit_step(bit_index=0):
            if bit_index >= len(bitstream):
                self.finish_transmission(sender, message)
                return
            
            current_bit = bitstream[bit_index]
            print(f"Transmitting bit {bit_index}: {current_bit} (Node {sender.node_id})")

            self.master.log_panel.append_bit(message) 
            self.animate_message_transmission(sender, receivers, message)

            for node in receivers:
                if node.mode == TRANSMITTING:
                    node_bit = node.transmit_bit()
                    if node_bit < current_bit:
                        arbitration_lost = True
                        sender.mode = RECEIVING 
                        node.mode = TRANSMITTING 
                        print(f"Node {sender.node_id} lost arbitration at bit {bit_index}")
                        break

            if not arbitration_lost:
                self.after(100, lambda: transmit_bit_step(bit_index + 1))
            else:
                print(f"Arbitration resolved. Node {sender.node_id} is now RECEIVING.")
                self.update_node_state(sender.node_id, transmitting=False)

        # Start bit-by-bit transmission
        sender.mode = TRANSMITTING
        self.update_node_state(sender.node_id, transmitting=True)
        transmit_bit_step()

    def finish_transmission(self, sender, message):
        print(f"Node {sender.node_id} completed message transmission: ID {message.identifier}")
        sender.mode = WAITING
        self.update_node_state(sender.node_id, transmitting=False)
        self.master.log_panel.add_log(f"Message {message.identifier} successfully sent by Node {sender.node_id}")


    def toggle_bus_activity(self, active=True):
        color = "yellow" if active else "lightgrey"
        self.canvas.itemconfig(self.bus_line, fill=color)

    def toggle_state_display(self):
        self.show_states = not self.show_states
        for node_id, label in self.node_info_labels.items():
            if self.show_states:
                node = self.nodes[node_id]
                info_text = (f"State: {node.state}\n"
                            f"Mode: {node.mode}\n"
                            f"TEC: {node.transmit_error_counter}\n"
                            f"REC: {node.receive_error_counter}")
                self.canvas.itemconfig(label, text=info_text)
            else:
                self.canvas.itemconfig(label, text="")

    def start_clock(self):
        #print("sahfshfsdgfhg")
        #print(self.clock_running)
        if self.clock_running: 
            self.clock_running = True
            self.update_clock()

    def update_clock(self):
        #print(f"Clock: {self.clock}")
        if self.clock_running:
            self.clock += 1
            self.display_clock()

            transmitting_node = None
            for node in self.nodes.values():
                if node.mode == TRANSMITTING and node.has_pending_message():
                    transmitting_node = node
                    break

            if transmitting_node:
                current_bit = transmitting_node.transmit_bit()

                message, bitstream = transmitting_node.message_queue[0]
                self.master.log_panel.display_bitstream_progress(bitstream, transmitting_node.current_bit_index)
            else:
                pass
                #self.master.log_panel.add_log(f"\nClock {self.clock}:No nodes transmitting.")

            self.after(500, self.update_clock) 

    def reset_clock(self):
        self.clock_running = False 
        self.clock = 0 
        self.display_clock() 

    def display_clock(self):
        self.canvas.itemconfig(self.clock_label, text=f"Clock = {self.clock}")

class LogPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = ctk.CTkTextbox(self.log_frame, state="disabled", wrap="none", height=200)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # self.scroll_y = ctk.CTkScrollbar(self.log_frame, command=self.log_text.yview)
        # self.scroll_y.grid(row=0, column=1, sticky="ns")

        # self.log_text.configure(yscrollcommand=self.scroll_y.set)
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)

        self.partial_bitstream = []
        self.current_position = 0
        self.field_positions = []

    def add_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def init_bitstream_display(self, message):
        self.partial_bitstream = []
        self.current_position = 0

        positions = message.calculate_bit_pos()
        bitstream = message.get_bitstream()

        self.field_positions = []
        for field, start_pos, end_pos in self._calculate_field_positions(positions, len(bitstream)):
            self.field_positions.append((field, start_pos, end_pos))
            self.partial_bitstream += [" "] * (end_pos - start_pos)

        headers = " | ".join(f"{field}".center(end - start) for field, start, end in self.field_positions)
        #self.clear_log()
        self.add_log("\nBus Data:")
        self.add_log(headers)
        self._update_bitstream_display()

    def _calculate_field_positions(self, positions, bitstream_length):
        field_positions = []
        for field, start in positions.items():
            next_field = list(positions.keys())[list(positions.keys()).index(field) + 1] if field != "EOF" else None
            end = positions[next_field] if next_field else bitstream_length
            field_positions.append((field, start, end))
        return field_positions

    def append_bit(self, message):
        bitstream = message.get_bitstream()
        error_index = message.error_bit_index

        if self.current_position < len(self.partial_bitstream):
            current_bit = str(bitstream[self.current_position])

            if self.current_position == error_index:
                self.partial_bitstream[self.current_position] = f"({current_bit})" 
            else:
                self.partial_bitstream[self.current_position] = current_bit 

            self.current_position += 1 

        self._update_bitstream_display()

    def _update_bitstream_display(self):
        visible_bits = ""
        for field, start, end in self.field_positions:
            segment_bits = "".join(self.partial_bitstream[start:end])
            visible_bits += f"{segment_bits} | "

        self.clear_log()
        headers = " | ".join(f"{field}".center(end - start) for field, start, end in self.field_positions)
        self.add_log("\nBus Data:")
        self.add_log(headers)
        self.add_log(visible_bits.strip(" | "))

class PredefinedScenarios(ctk.CTkFrame):
    def __init__(self, master, playground):
        super().__init__(master)
        self.master = master
        self.playground = playground

        self.active_scenario = None
        self.run_active = False 

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        title_frame = ctk.CTkFrame(self)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(title_frame, text="Predefined Scenarios in CAN", font=("Arial", 20, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame, text="Go to Interactive Simulation", command=self.master.show_interactive_simulation).pack(side="right", padx=10)

        left_column = ctk.CTkFrame(self)
        left_column.grid(row=1, column=0, sticky="ns", padx=10, pady=10)

        control_row = ctk.CTkFrame(left_column)
        control_row.pack(fill="x", pady=5)
        ctk.CTkButton(control_row, text="Run", command=self.run_scenario).pack(side="left", padx=20)
        #ctk.CTkButton(control_row, text="Pause", command=self.pause_scenario).pack(side="left", padx=5)
        ctk.CTkButton(control_row, text="Reset", command=self.reset_scenario).pack(side="right", padx=20)

        #toggle_states_row = ctk.CTkFrame(left_column)
        #toggle_states_row.pack(fill="x", pady=(10, 50))
        #ctk.CTkButton(toggle_states_row, text="Toggle States", command=self.playground.toggle_state_display).pack(padx=5)

        self.initialize_scenario_menu(left_column)

        self.playground = Playground(self, self.master)
        self.playground.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.log_panel = LogPanel(self)
        self.log_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        self.initialize_predefined_scenarios()

    def initialize_scenario_menu(self, parent):
        scenario_menu = ctk.CTkFrame(parent)
        scenario_menu.pack(fill="x", pady=10)

        self.frame_dropdown = ctk.CTkOptionMenu(
            scenario_menu,
            values=["Data Frame", "Remote Frame", "Error Frame"],
            command=self.select_frame
        )
        self.frame_dropdown.pack(fill="x", pady=5)

        self.arbitration_btn = ctk.CTkButton(
            scenario_menu,
            text="Arbitration Test",
            command=self.select_arbitration
        )
        self.arbitration_btn.pack(fill="x", pady=5)

        self.error_dropdown = ctk.CTkOptionMenu(
            scenario_menu,
            values=["Bit Monitor Error", "Cyclic Redundancy Check Error", "Bit Stuff Error", "Form Error", "Acknowledgment Error"],
            command=self.select_error
        )
        self.error_dropdown.pack(fill="x", pady=5)

        self.node_failure_btn = ctk.CTkButton(
            scenario_menu,
            text="Node Failure Test",
            command=self.select_node_failure
        )
        self.node_failure_btn.pack(fill="x", pady=5)

        self.scenario_explanation = ctk.CTkLabel(
            scenario_menu, text="Select a scenario to see its details", font=("Arial", 12), width=380, wraplength=380
        )
        self.scenario_explanation.pack(fill="x", pady=(10, 0))

    def select_frame(self, frame_type):
        self.active_scenario = "frame"
        explanations = {
            "Data Frame": "Demonstrates the basic transfer of data between nodes in a CAN network.",
            "Remote Frame": "Used to request data from another node in the CAN network.",
            "Error Frame": "Shows how error frames are transmitted when an error is detected on the bus."
        }
        self.scenario_explanation.configure(text=f"Frame: {frame_type} - {explanations[frame_type]}")

    def select_arbitration(self):
        self.active_scenario = "arbitration"
        self.scenario_explanation.configure(
            text="Arbitration Test: Demonstrates how nodes resolve conflicts when multiple nodes try to transmit simultaneously."
        )

    def select_error(self, error_type):
        self.active_scenario = "error"
        explanations = {
            "Bit Monitor Error": "Occurs when a transmitter detects an inconsistency in the transmitted bit.",
            "Cyclic Redundancy Check Error": "Detected when the CRC check fails.",
            "Bit Stuff Error": "Detected when the stuffing rule (5 consecutive bits of the same polarity) is violated.",
            "Form Error": "Occurs when a fixed format field contains an illegal value.",
            "Acknowledgment Error": "Occurs when a transmitter does not receive an ACK."
        }
        self.scenario_explanation.configure(text=f"Error: {error_type} - {explanations[error_type]}")

    def select_node_failure(self):
        self.active_scenario = "node_failure"
        #self.disable_other_scenarios("node_failure")
        self.scenario_explanation.configure(
            text="Node Failure Test: Tests how a node transitions to error-passive and bus-off states."
        )

    def disable_other_scenarios(self, active_scenario):
        self.frame_dropdown.configure(state="disabled" if active_scenario != "frame" else "normal")
        self.arbitration_btn.configure(state="disabled" if active_scenario != "arbitration" else "normal")
        self.error_dropdown.configure(state="disabled" if active_scenario != "error" else "normal")
        self.node_failure_btn.configure(state="disabled" if active_scenario != "node_failure" else "normal")

    def run_scenario(self):
        self.playground.clock_running = True
        if self.active_scenario == "frame":
            #self.log_panel.add_log(f"Running message transmission ({self.frame_dropdown.get()})...")
            self.run_data_frame()
        elif self.active_scenario == "arbitration":
            self.run_arbitration_test()
        elif self.active_scenario == "error":
            selected_error = self.error_dropdown.get()
            self.log_panel.add_log(f"Injecting {selected_error}...")
            #logic
            if selected_error == "Bit Monitor Error":
                self.log_panel.add_log("Simulating a Bit Monitor Error on the bus...")
                #monitor err
            elif selected_error == "Cyclic Redundancy Check Error":
                self.log_panel.add_log("Simulating a CRC Error...")
                #crc err
            elif selected_error == "Bit Stuff Error":
                self.log_panel.add_log("Simulating a Bit Stuff Error...")
                #stuff err
            elif selected_error == "Form Error":
                self.log_panel.add_log("Simulating a Form Error...")
                #form err
            elif selected_error == "Acknowledgment Error":
                self.log_panel.add_log("Simulating an Acknowledgment Error...")
                #ack err
        elif self.active_scenario == "node_failure":
            self.log_panel.add_log("Running Node Failure Test...")
            #node failure
        else:
            self.log_panel.add_log("No scenario selected. Please select a scenario to run.")

    def pause_scenario(self):
        self.log_panel.add_log("Pausing scenario...")

    def reset_scenario(self):
        self.run_active = False
        self.playground.reset()
        self.log_panel.clear_log()
        self.active_scenario = None
        self.playground.reset_clock()
        self.playground.clock_running = False

    def initialize_predefined_scenarios(self):
        self.playground.reset()
        component_names = list(COMPONENTS.keys())

        for i in range(12):
            self.playground.add_node(node_id=i + 1)
            component_name = component_names[i % len(component_names)]

            self.playground.assign_node_to_component(i + 1, component_name)
        

    def run_data_frame(self):
        self.log_panel.add_log("Starting Data Frame Transmission...")

        sender = random.choice(list(self.playground.nodes.values()))
        receivers = [n for n in self.playground.nodes.keys() if n != sender]

        message = DataFrame(
            identifier=random.choice(sender.produced_ids), 
            sent_by=sender.node_id, 
            data=[random.randint(0, 255)] 
        )

        sender.add_message_to_queue(message)

        #self.log_panel.add_log(f"Node {sender} is transmitting Message ID: {message.identifier}")
        print(repr(message))
        print(message.get_bitstream())
        self.log_panel.init_bitstream_display(message)
        #self.playground.start_clock()
        self.playground.process_bits(sender, message)

    def run_arbitration_test(self):
        self.log_panel.add_log("Starting Arbitration Test...")
        senders = random.sample(list(self.playground.nodes.keys()), 3)

        for sender in senders:
            message = DataFrame(identifier=random.randint(0, 10), sent_by=sender, data=[random.randint(0, 255)])
            self.playground.nodes[sender].add_message_to_queue(message)

        self.log_panel.add_log(f"Nodes {senders} are competing for arbitration...")
        self.playground.start_clock()

    def run_node_failure(self):
        self.log_panel.add_log("Starting Node Failure Test...")
        node = random.choice(list(self.playground.nodes.keys()))
        self.playground.nodes[node].state = "Error Passive"
        self.log_panel.add_log(f"Node {node} has transitioned to Error Passive state.")
        self.playground.start_clock() 


class InteractiveSimulation(ctk.CTkFrame):
    def __init__(self, master, playground):
        super().__init__(master)
        self.master = master
        self.playground = playground
        self.nodes = []
        self.bus = playground.bus 
        self.message_load = MEDIUM 
        self.messages_sent = 0

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        title_frame = ctk.CTkFrame(self)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(title_frame, text="Interactive Simulation of CAN", font=("Arial", 20, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame, text="Go to Predefined Scenarios", command=self.master.show_predefined_scenarios).pack(side="right", padx=10)

        left_column = ctk.CTkFrame(self)
        left_column.grid(row=1, column=0, sticky="ns", padx=10, pady=10)

        control_row = ctk.CTkFrame(left_column)
        control_row.pack(fill="x", pady=5)
        ctk.CTkButton(control_row, text="Run", command=self.run_simulation).pack(side="left", padx=20)
        #ctk.CTkButton(control_row, text="Pause", command=self.pause_scenario).pack(side="left", padx=5)
        ctk.CTkButton(control_row, text="Reset", command=self.reset_simulation).pack(side="right", padx=20)

        #toggle_states_row = ctk.CTkFrame(left_column)
        #toggle_states_row.pack(fill="x", pady=(10, 50)) 
        #ctk.CTkButton(toggle_states_row, text="Toggle States", command=self.playground.toggle_state_display).pack(padx=5)

        interactive_menu = ctk.CTkFrame(left_column)
        interactive_menu.pack(fill="x", pady=10)
        ctk.CTkButton(interactive_menu, text="Edit Node Configuration", command=self.edit_node_config).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Send Custom Message", command=self.open_custom_message_window).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Inject Errors", command=self.inject_errors).pack(fill="x", pady=5)
        load_menu = ctk.CTkFrame(left_column)
        load_menu.pack(fill="x", pady=10)
        ctk.CTkLabel(load_menu, text="Message Load:").pack(anchor="w")
        self.load_dropdown = ctk.CTkOptionMenu(
            load_menu,
            values=["Low", "Medium", "High"],
            command=self.set_message_load
        )
        self.load_dropdown.set("Medium")
        self.load_dropdown.pack(fill="x", pady=5)

        self.playground = Playground(self, master)
        self.playground.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.log_panel = LogPanel(self)
        self.log_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        self.initialize_nodes()

    def add_node(self, node_id=None, position=None):
        node_id = node_id or self.next_node_id

    def initialize_nodes(self):
        for i in range(5): 
            self.playground.add_node(node_id=i + 1)
            node = CANNode(i + 1, self.playground.bus)
            self.nodes.append(node)
        self.log_panel.add_log("Initialized simulation with 5 nodes on the CAN bus.")

    def broadcast_message(self):
        sender_id = 1  
        self.log_panel.add_log(f"Broadcasting message from Node {sender_id} to all nodes...")
        for receiver_id in self.playground.nodes:
            if receiver_id != sender_id: 
                self.playground.animate_message(sender_id, receiver_id)
                self.log_panel.add_log(f"Node {receiver_id} received the message.")
        
    def open_custom_message_window(self):
        if not self.nodes:
            self.log_panel.add_log("No nodes available to send messages")
            return
        window = ctk.CTkToplevel(self)
        window.title("Send Custom Message")
        window.geometry("500x400")

        sender_label = ctk.CTkLabel(window, text="Sender Node:")
        sender_label.pack(pady=5)
        for node in self.nodes:
            sender_var = ctk.StringVar(value=list(node.node_id)[0])
            sender_menu = ctk.CTkOptionMenu(window, variable=sender_var, values=list(map(str, node.node_id)))
        sender_menu.pack(pady=5)

        receiver_label = ctk.CTkLabel(window, text="Receivers (multi-select):")
        receiver_label.pack(pady=5)
        receiver_vars = {node_id: ctk.BooleanVar() for node_id in self.nodes}
        for node_id, var in receiver_vars.items():
            ctk.CTkCheckBox(window, text=f"Node {node_id}", variable=var).pack(anchor="w")

        error_label = ctk.CTkLabel(window, text="Inject Error (optional):")
        error_label.pack(pady=5)
        error_var = ctk.StringVar(value="None")
        error_menu = ctk.CTkOptionMenu(window, variable=error_var, values=["None", "Bit Monitoring", "Bit Stuffing", "Acknowledgement Error", "CRC Error", "Frame Error"])
        error_menu.pack(pady=5)

        def send_message():
            sender_id = int(sender_var.get())
            receivers = [node_id for node_id, var in receiver_vars.items() if var.get()]
            error_type = error_var.get() if error_var.get() != "None" else None
            self.log_panel.add_log(f"Sending message from Node {sender_id} to {receivers} with error: {error_type}")
            window.destroy()

        ctk.CTkButton(window, text="Send", command=send_message).pack(pady=10)

    def set_message_load(self, load_level):
        self.message_load = load_level
        self.log_panel.add_log(f"Message load set to {load_level}.")

    def run_simulation(self):
        num_nodes = len(self.playground.nodes)
        if self.message_load == "Low":
            max_messages = num_nodes
        elif self.message_load == "Medium":
            max_messages = num_nodes * 2
        elif self.message_load == "High":
            max_messages = num_nodes * 4
        else:
            max_messages = num_nodes

        for i in range(max_messages):
            sender = random.choice(list(self.playground.nodes.keys()))
            receivers = [n for n in self.playground.nodes if n != sender]
            receiver = random.choice(receivers) if receivers else None

            if receiver:
                message = f"Message from Node {sender} to Node {receiver}"
                self.master.add_to_message_queue(message)
                self.log_panel.add_log(f"Added: {message}")

        self.log_panel.add_log("Simulation started.")

    def reset_simulation(self):
        self.playground.reset()
        self.log_panel.clear_log()
        self.playground.reset_clock()
        self.playground.clock_running = False

    def pause_simulation(self):
        self.log_panel.add_log("Pause button")

    def edit_node_config(self):
        window = ctk.CTkToplevel(self)
        window.title("Edit Configuration")
        window.geometry("600x500")

        components = [f"Component {i + 1}" for i in range(len(self.playground.components))]
        components.append("Add New Component") 

        ctk.CTkLabel(window, text="Select Node:").pack(pady=5)
        node_var = ctk.StringVar(value="Select a Node")
        node_dropdown = ctk.CTkOptionMenu(
            window, variable=node_var,
            values=[f"Node {node_id}" for node_id in self.playground.nodes.keys()],
            command=lambda _: update_node_properties(node_var.get())
        )
        node_dropdown.pack(pady=5)

        ctk.CTkLabel(window, text="Component:").pack(pady=5)
        component_var = ctk.StringVar(value="Select Component")
        component_dropdown = ctk.CTkOptionMenu(
            window, variable=component_var,
            values=components,
            command=lambda _: handle_component_selection(component_var.get())
        )
        component_dropdown.pack(pady=5)

        filter_label = ctk.CTkLabel(window, text="Filters (comma-separated):")
        filter_label.pack(pady=5)
        filter_entry = ctk.CTkEntry(window)
        filter_entry.pack(pady=5)

        def update_node_properties(node_selection):
            node_id = int(node_selection.split()[1])
            node = self.playground.nodes[node_id]
            component_name = next(
                (name for name, node_ids in self.playground.components.items() if node_id in node_ids),
                "Select Component"
            )
            component_var.set(component_name)
            filter_entry.delete(0, "end")
            filter_entry.insert(0, ",".join(map(str, node.filters)))

        def handle_component_selection(selection):
            if selection == "Add New Component":
                new_component_name = f"Component {len(self.playground.components) + 1}"
                self.playground.add_component(new_component_name)
                component_dropdown.configure(values=components + [new_component_name])
                component_var.set(new_component_name)

        def save_changes():
            node_id = int(node_var.get().split()[1])
            if node_id not in self.playground.nodes:
                print("Invalid node selected.")
                return

            filters = list(map(int, filter_entry.get().split(",")))
            self.playground.nodes[node_id].filters = filters

            component_name = component_var.get()
            if component_name != "Select Component":
                self.playground.assign_node_to_component(node_id, component_name)

            print(f"Node {node_id} updated: Filters={filters}, Component={component_name}")

        def delete_node():
            node_id = int(node_var.get().split()[1])
            if node_id in self.playground.nodes:
                del self.playground.nodes[node_id]
                for node_ids in self.playground.components.values():
                    if node_id in node_ids:
                        node_ids.remove(node_id)
                node_dropdown.configure(
                    values=[f"Node {node_id}" for node_id in self.playground.nodes.keys()]
                )
                print(f"Node {node_id} deleted.")

        def add_new_node():
            self.playground.add_node()
            node_dropdown.configure(
                values=[f"Node {node_id}" for node_id in self.playground.nodes.keys()]
            )

        ctk.CTkButton(window, text="Save Changes", command=save_changes).pack(pady=10)
        ctk.CTkButton(window, text="Delete Node", command=delete_node).pack(pady=10)
        ctk.CTkButton(window, text="Add New Node", command=add_new_node).pack(pady=10)

    def send_custom_message(self):
        self.log_panel.add_log("Sending custom message button")

    def inject_errors(self):
        self.log_panel.add_log("Injecting errors button")

    def modify_network_load(self):
        self.log_panel.add_log("Modifying network load button")

if __name__ == "__main__":
    app = CANSimulatorApp()
    app.mainloop()