import customtkinter as ctk
from can_bus import CANBus
from can_node import CANNode
import time

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class CANSimulatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CAN Simulator Project")
        self.geometry("1200x800")

        self.playground = Playground(self, self)
        self.predefined_scenarios = PredefinedScenarios(self, self.playground)
        self.interactive_simulation = InteractiveSimulation(self, self.playground)

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
        self.show_states = True

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(self, bg="black", scrollregion=(0, 0, 2000, 1000))
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.bus_line = self.canvas.create_line(50, 580, 2050, 580, fill="lightgrey", width=5)
        self.canvas.create_text(80, 560, text="CAN Bus", fill="white", font=('Arial', 14, 'bold'))

    def add_node(self, node_id=None, position=None):
        if len(self.nodes) >= self.max_nodes:
            return

        node_id = node_id or self.next_node_id
        x_position = 150 + len(self.nodes) * 150
        y_position = 450 if len(self.nodes) % 2 == 0 else 710  
        position = (x_position, y_position)

        node = CANNode(node_id, self.bus)
        node.state = "Error Active"
        node.mode = "Waiting"
        node.transmit_error_counter = 0
        node.receive_error_counter = 0

        self.nodes[node_id] = node
        self.node_positions[node_id] = position
        self.next_node_id += 1
        self.draw_nodes()

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
            top = y - node_height if y < 580 else y
            bottom = y if y < 580 else y + node_height

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
                x, bottom if y < 580 else top, x, 580, width=2, fill="grey"
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
                x, top - 20 if y < 580 else bottom + 20, text=f"Node {node_id}", fill="lightgrey", font=("Arial", 14, "bold")
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

    def toggle_bus_activity(self, active=True):
        color = "yellow" if active else "lightgrey"
        self.canvas.itemconfig(self.bus_line, fill=color)


    def toggle_state_display(self):
        self.show_states = not self.show_states
        for node_id, label in self.node_info_labels.items():
            if self.show_states:
                # Restore the text with node details
                node = self.nodes[node_id]
                info_text = (f"State: {node.state}\n"
                            f"Mode: {node.mode}\n"
                            f"TEC: {node.transmit_error_counter}\n"
                            f"REC: {node.receive_error_counter}")
                self.canvas.itemconfig(label, text=info_text)
            else:
                # Hide the text by setting it to an empty string
                self.canvas.itemconfig(label, text="")

class LogPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.log_text = ctk.CTkTextbox(self, state="disabled", height=100)
        self.log_text.pack(expand=True, fill="both", padx=10, pady=10)

    def add_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

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
        """Disable other options based on the active scenario."""
        self.frame_dropdown.configure(state="disabled" if active_scenario != "frame" else "normal")
        self.arbitration_btn.configure(state="disabled" if active_scenario != "arbitration" else "normal")
        self.error_dropdown.configure(state="disabled" if active_scenario != "error" else "normal")
        self.node_failure_btn.configure(state="disabled" if active_scenario != "node_failure" else "normal")

    def run_scenario(self):
        if self.active_scenario == "frame":
            self.log_panel.add_log(f"Running message transmission ({self.frame_dropdown.get()})...")
            #logic
        elif self.active_scenario == "arbitration":
            self.log_panel.add_log("Running arbitration test...")
            #logic
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

    def initialize_predefined_scenarios(self):
        self.playground.reset()
        for i in range(12):
            self.playground.add_node(node_id=i + 1)

class InteractiveSimulation(ctk.CTkFrame):
    def __init__(self, master, playground):
        super().__init__(master)
        self.master = master
        self.playground = playground

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
        ctk.CTkButton(interactive_menu, text="Send Custom Message", command=self.send_custom_message).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Inject Errors", command=self.inject_errors).pack(fill="x", pady=5)
        ctk.CTkButton(interactive_menu, text="Modify Network Load", command=self.modify_network_load).pack(fill="x", pady=5)

        self.playground = Playground(self, master)
        self.playground.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.log_panel = LogPanel(self)
        self.log_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

    def add_node(self, node_id=None, position=None):
        node_id = node_id or self.next_node_id
        
    def open_custom_message_window(self):
        if not self.nodes:
            self.log_panel.add_log("No nodes available to send messages")
            return
        window = ctk.CTkToplevel(self)
        window.title("Send Custom Message")
        window.geomtry("500x400")

        sender_label = ctk.CTkLabel(window, text="Sender Node:")
        sender_label.pack(pady=5)
        sender_var = ctk.StringVar(value=list(self.nodes.keys())[0])
        sender_menu = ctk.CTkOptionMenu(window, variable=sender_var, values=list(map(str, self.nodes.keys())))
        sender_menu.pack(pady=5)

        receiver_label = ctk.CTkLabel(window, text="Receivers (multi-select):")
        receiver_label.pack(pady=5)
        receiver_vars = {node_id: ctk.BooleanVar() for node_id in self.nodes}
        for node_id, var in receiver_vars.items():
            ctk.CTkCheckBox(window, text=f"Node {node_id}", variable=var).pack(anchor="w")

        error_label = ctk.CTkLabel(window, text="Inject Error (optional):")
        error_label.pack(pady=5)
        error_var = ctk.StringVar(value="None")
        error_menu = ctk.CTkOptionMenu(window, variable=error_var, values=["None", "Bit Error", "CRC Error", "Frame Error"])
        error_menu.pack(pady=5)

        def send_message():
            sender_id = int(sender_var.get())
            receivers = [node_id for node_id, var in receiver_vars.items() if var.get()]
            error_type = error_var.get() if error_var.get() != "None" else None
            self.log_panel.add_log(f"Sending message from Node {sender_id} to {receivers} with error: {error_type}")
            window.destroy()

        ctk.CTkButton(window, text="Send", command=send_message).pack(pady=10)

    def run_simulation(self):
        self.log_panel.add_log("Running simulation...")

    def pause_simulation(self):
        self.log_panel.add_log("Pausing simulation...")

    def reset_simulation(self):
        self.playground.reset()
        self.log_panel.clear_log()

    def edit_node_config(self):
        self.log_panel.add_log("Editing node configuration...")

    def send_custom_message(self):
        self.log_panel.add_log("Sending custom message...")

    def inject_errors(self):
        self.log_panel.add_log("Injecting errors...")

    def modify_network_load(self):
        self.log_panel.add_log("Modifying network load...")

if __name__ == "__main__":
    app = CANSimulatorApp()
    app.mainloop()
