import tkinter as tk
import asyncio
from can_bus import CANBus
from can_node import CANNode

class CANSimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CAN Network Simulation")
        self.geometry("700x500")

        self.canvas = tk.Canvas(self, width=600, height=400, bg="white")
        self.canvas.pack(pady=20)

        self.bus_line = self.canvas.create_line(100, 200, 500, 200, fill="black", width=3)
        self.canvas.create_text(300, 180, text="CAN Bus", fill="black", font=('Times New Roman', 12, 'bold'))
        self.bus = CANBus()

        self.nodes = {
            1: CANNode(1, self.bus),
            2: CANNode(2, self.bus),
            3: CANNode(3, self.bus)
        }

        for node in self.nodes.values():
            self.bus.add_node(node)

        self.node_positions = {1: (100, 100), 2: (500, 100), 3: (300, 300)}
        for node_id, pos in self.node_positions.items():
            x, y = pos
            self.canvas.create_oval(x-20, y-20, x+20, y+20, fill="lightgrey", outline="black")
            # self.canvas.create_text(x, y, text=f"Node {node_id}", font={'Times New Roman', 10})
            if y < 200: 
                y = y + 20
            else: 
                y = y - 20
            self.canvas.create_line(x, y, x, 200, width=2, fill="gray") 

        control_frame = tk.Frame(self)
        control_frame.pack()

        for node_id in self.nodes:
            btn = tk.Button(control_frame, text=f"Send from node {node_id}", command=lambda n=node_id: self.send_message(n, 10, [1, 2, 3, 4]))    
            btn.pack(side=tk.LEFT, padx=5)

    def send_message(self, node_id, message_id, data):
        node = self.nodes[node_id]
        node.send_message(message_id, data)
        self.animate_message_to_bus(node_id)

    def animate_message_to_bus(self, node_id):
        pos = self.node_positions[node_id]
        bus_pos = (pos[0], 200)

        message_circle = self.canvas.create_oval(pos[0]-5, pos[1]-5, pos[0]+5, pos[1]+5, fill="light pink")
        self.move_to_pos(message_circle, pos, bus_pos, lambda: self.activate_bus_line(message_circle, node_id))

    def activate_bus_line(self, message_circle, node_id):
        self.canvas.itemconfig(self.bus_line, fill = "light pink")
        self.canvas.delete(message_circle)

        def move_and_delete_circle(circle, start, end):
            self.move_to_pos(circle, start, end, lambda: self.canvas.delete(circle))

        for nodes, pos in self.node_positions.items():
            if nodes != node_id: 
                bus_pos = (pos[0], 200) 
                new_circle = self.canvas.create_oval(bus_pos[0]-5, bus_pos[1]-5, bus_pos[0]+5, bus_pos[1]+5, fill="light pink")
                move_and_delete_circle(new_circle, bus_pos, pos)

        self.after(1000, lambda: self.canvas.itemconfig(self.bus_line, fill="black"))

    def move_to_pos(self, item, start, end, callback=None):
        x1, y1 = start
        x2, y2 = end
        dx = (x2 - x1) / 20
        dy = (y2 - y1) / 20

        def animate_step():
            nonlocal x1, y1
            x1 += dx
            y1 += dy
            self.canvas.coords(item, x1-5, y1-5, x1+5, y1+5)

            if abs(x1-x2) <= abs(dx) and abs(y1-y2) <= abs(dy):
                self.canvas.coords(item, x2-5, y2-5, x2+5, y2+5)
                if callback:
                    callback()
            else:
                self.after(50, animate_step)

        animate_step()

if __name__ == "__main__":
    app = CANSimulatorApp()
    app.mainloop()
