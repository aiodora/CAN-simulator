from manim import *

class CANMessageFlow(Scene):
    """Visualizes the message flow on the CAN bus."""
    def construct(self):
        # Create nodes
        node1 = Circle(radius=0.5, color=BLUE).shift(LEFT * 3)
        node2 = Circle(radius=0.5, color=GREEN).shift(ORIGIN)
        node3 = Circle(radius=0.5, color=RED).shift(RIGHT * 3)

        # Add labels
        label1 = Text("Node 1").next_to(node1, UP)
        label2 = Text("Node 2").next_to(node2, UP)
        label3 = Text("Node 3").next_to(node3, UP)

        # Add nodes and labels
        self.play(Create(node1), Write(label1))
        self.play(Create(node2), Write(label2))
        self.play(Create(node3), Write(label3))

        # Message flow animation
        message = Text("Message", color=YELLOW).scale(0.7)
        self.play(FadeIn(message.move_to(node1.get_center())))
        self.play(message.animate.move_to(node2.get_center()))
        self.play(message.animate.move_to(node3.get_center()))
        self.wait(2)
        self.play(FadeOut(message))


class CANArbitration(Scene):
    """Visualizes the arbitration process in a CAN network."""
    def construct(self):
        # Create nodes and IDs
        node1 = Circle(radius=0.5, color=BLUE).shift(LEFT * 3)
        node2 = Circle(radius=0.5, color=GREEN).shift(ORIGIN)
        node3 = Circle(radius=0.5, color=RED).shift(RIGHT * 3)

        id1 = Text("110").next_to(node1, DOWN)
        id2 = Text("101").next_to(node2, DOWN)
        id3 = Text("011").next_to(node3, DOWN)

        # Add nodes and IDs
        self.play(Create(node1), Write(id1))
        self.play(Create(node2), Write(id2))
        self.play(Create(node3), Write(id3))

        # Arbitration process (highlight the winner)
        self.play(
            Indicate(node3, color=YELLOW),
            Write(Text("Node 3 wins!").next_to(node3, UP, buff=0.5))
        )
        self.wait(2)


class CANErrorDetection(Scene):
    """Visualizes error detection in CAN communication."""
    def construct(self):
        # Create nodes
        node1 = Circle(radius=0.5, color=BLUE).shift(LEFT * 3)
        node2 = Circle(radius=0.5, color=GREEN).shift(ORIGIN)

        label1 = Text("Node 1").next_to(node1, UP)
        label2 = Text("Node 2").next_to(node2, UP)

        # Add nodes
        self.play(Create(node1), Write(label1))
        self.play(Create(node2), Write(label2))

        # Message with error
        message = Text("Message with CRC Error", color=RED).scale(0.7)
        self.play(FadeIn(message.move_to(node1.get_center())))
        self.play(message.animate.move_to(node2.get_center()))
        self.play(FadeOut(message))

        # Show error frame
        error_frame = Text("Error Frame", color=RED).scale(0.7).move_to(node2.get_center())
        self.play(FadeIn(error_frame))
        self.wait(2)
        self.play(FadeOut(error_frame))


class CANFrameBreakdown(Scene):
    """Explains the structure of a CAN frame."""
    def construct(self):
        # Fields of a CAN frame
        fields = [
            ("Start of Frame (SOF)", BLUE),
            ("Arbitration Field", GREEN),
            ("Control Field", YELLOW),
            ("Data Field", RED),
            ("CRC Field", ORANGE),
            ("ACK Field", PURPLE),
            ("End of Frame (EOF)", GREY),
        ]

        # Create rectangles for each field
        x_start = -6
        y_start = 0
        width = 1.5
        height = 1
        spacing = 0.2

        rectangles = []
        for field, color in fields:
            rect = Rectangle(
                width=width, height=height, color=color, fill_opacity=0.5
            ).shift(RIGHT * x_start)
            label = Text(field, color=color).scale(0.4).next_to(rect, DOWN, buff=0.1)
            self.play(Create(rect), Write(label))
            rectangles.append(rect)
            x_start += width + spacing

        self.wait(2)


class CANPredefinedScenarios(Scene):
    """Visualizes a predefined scenario like node failure and recovery."""
    def construct(self):
        # Create nodes
        node1 = Circle(radius=0.5, color=BLUE).shift(LEFT * 3)
        node2 = Circle(radius=0.5, color=GREEN).shift(ORIGIN)
        node3 = Circle(radius=0.5, color=RED).shift(RIGHT * 3)

        # Labels
        label1 = Text("Node 1").next_to(node1, UP)
        label2 = Text("Node 2").next_to(node2, UP)
        label3 = Text("Node 3").next_to(node3, UP)

        # Add nodes and labels
        self.play(Create(node1), Write(label1))
        self.play(Create(node2), Write(label2))
        self.play(Create(node3), Write(label3))

        # Node failure
        self.play(FadeOut(node2), Write(Text("Node 2 Failed!").move_to(node2.get_center())))
        self.wait(1)

        # Recovery
        self.play(FadeIn(node2), Write(Text("Node 2 Recovered!").move_to(node2.get_center())))
        self.wait(2)
