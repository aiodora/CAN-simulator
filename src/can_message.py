class CANMessage:
    def __init__(self, identifier, data=None, frame_type="Data"):
        self.start_of_frame = 1 
        self.identifier = identifier
        self.frame_type = frame_type
        if frame_type == "Data": self.rtr = 0
        else: self.rtr = 1
        self.control_field = self.calculate_control_field(data)
        if data: self.data_field = data
        else: self.data_field = []
        self.crc = self.calculate_crc()
        self.crc_delimiter = 1
        self.ack_slot = 1 
        self.ack_delimiter = 1 
        self.end_of_frame = [1] * 7 
        self.intermission = [1] * 3

    def calculate_control_field(self, data):
        if data: data_length_code = min(len(data), 8)
        else: data_length_code = 0
        data_length_code_bits = f"{data_length_code:04b}"

        ide_bit = "0"
        reserved_bit = "0"

        control_field = data_length_code_bits + ide_bit + reserved_bit 

        return control_field

    def calculate_crc(self): 
        polynomial = 0b1100000000000011
        crc = 0

        bitstream = (
            [self.start_of_frame] +
            [int(b) for b in f"{self.identifier:011b}"] + 
            [self.rtr] +
            [int(b) for b in self.control_field]
        )

        for i in range(len(bitstream) - 15):
            if bitstream[i] == 1:
                for j in range(16): 
                    bitstream[i + j] ^= (polynomial >> (15 - j)) & 1

        crc_bits = bitstream[-15:]
        crc = int("".join(map(str, crc_bits)), 2)

        return crc
    
    def __repr__(self):
        return (f"CANMessage(id={self.identifier}, data={self.data_field}, "
                f"crc={self.crc}, frame_type={self.rtr})")
    
class DataFrame(CANMessage):
    def __init__(self, identifier, data):
        super().__init__(identifier, data, frame_type="Data")

class RemoteFrame(CANMessage):
    def __init__(self, identifier):
        super().__init__(identifier, data=None, frame_type="Remote")

class ErrorFrame(CANMessage):
    def __init__(self):
        super().__init__(identifier=None, data=None, frame_type="Error")

class OverloadFrame(CANMessage):
    def __init__(self):
        super().__init__(identifier=None, data=None, frame_type="Overload")
        self.overload_flag = [1] * 6
        