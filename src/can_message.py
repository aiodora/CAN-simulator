import random

class CANMessage:
    def __init__(self, identifier, sent_by, data=None, frame_type="Data"):
        self.start_of_frame = [0] 
        self.identifier = identifier
        self.frame_type = frame_type
        if frame_type == "Data": self.rtr = [0]
        else: self.rtr = [1]
        self.control_field = self.calculate_control_field(data)
        if data: self.data_field = data #at most 8 bytes
        else: self.data_field = []
        self.crc = self.calculate_crc()
        self.crc_delimiter = [1]
        self.ack_slot = 1 
        self.ack_delimiter = [1]
        self.end_of_frame = [1] * 7
        self.intermission = [1] * 3
        self.error_type = None
        self.sender_id = sent_by
        self.bit_flipped = [None, None]
        self.error_bit_index = None 

    def calculate_control_field(self, data):
        if data: data_length_code = min(len(data), 8)
        else: data_length_code = 0
        data_length_code_bits = f"{data_length_code:04b}"

        ide_bit = "0"
        reserved_bit = "0"

        control_field = data_length_code_bits + ide_bit + reserved_bit 

        return control_field

    def calculate_crc(self): 
        if self.identifier is None:
            return 0
        
        polynomial = 0b1100000000000011
        crc = 0

        bitstream = (
            [self.start_of_frame] +
            [int(b) for b in f"{self.identifier:011b}"] + 
            self.rtr +
            [int(b) for b in self.control_field]
        )

        for i in range(len(bitstream) - 15):
            if bitstream[i] == 1:
                for j in range(16): 
                    bitstream[i + j] ^= (polynomial >> (15 - j)) & 1

        crc_bits = bitstream[-15:]
        crc = int("".join(map(str, crc_bits)), 2)

        return crc
    
    def apply_bit_stuffing(self, bitstream):
        stuffed_bits = []
        consecutive_bits = 1
        last_bit = bitstream[0]
        for bit in bitstream[1:]:
            if bit == last_bit:
                consecutive_bits += 1
            else:
                consecutive_bits = 1
            stuffed_bits.append(last_bit)
            if consecutive_bits == 6:
                stuffed_bits.append(1 - last_bit) 
                consecutive_bits = 1
            last_bit = bit
        stuffed_bits.append(last_bit)
        return stuffed_bits
    
    def get_bitstream(self):
        bitstream = []
        
        bitstream.append(self.start_of_frame)
        
        if self.identifier is not None:
            identifier_bits = [int(b) for b in f"{self.identifier:011b}"]
            bitstream.extend(identifier_bits)

        bitstream.append(self.rtr)
        
        control_field_bits = [int(b) for b in self.control_field]
        bitstream.extend(control_field_bits)
        
        if self.data_field:
            for byte in self.data_field: 
                byte_bits = [int(b) for b in f"{byte:08b}"]
                bitstream.extend(byte_bits)

        crc_bits = [int(b) for b in f"{self.crc:015b}"]
        bitstream.extend(crc_bits)

        bitstream.append(self.crc_delimiter)
        bitstream.append(self.ack_slot)
        bitstream.append(self.ack_delimiter)
        bitstream.append(self.end_of_frame)
        bitstream.append(self.intermission)

        if self.error_type != "stuff_error":
            bitstream = self.apply_bit_stuffing(bitstream)

        return bitstream
    
    def get_ack_index(self):
        base_length = 1 + 11 + 1 + 6 + 15 + 1  #SOF + ID + RTR + Control + CRC + CRC_DELIM
        data_length = 8 * len(self.data_field)
        ack_index = base_length + data_length 
        return ack_index
    
    def __repr__(self):
        if(self.identifier != None):
            return (f"CANMessage(type={self.frame_type}, id={self.identifier}, data={self.data_field}, crc={self.crc}, frame_type={self.rtr}), ack_slot={self.ack_slot}")
        else: 
            return (f"CANMessage(type={self.frame_type}")
    
    #monitor error; to refine
    def corrupt_bit(self):
        bitstream = self.get_bitstream()
        identifier_length = 11 
        start_of_corruptible_bits = identifier_length + 2 
        
        if len(bitstream) > start_of_corruptible_bits:
            bit_to_flip = random.randint(start_of_corruptible_bits, len(bitstream) - 1)
            self.bit_flipped = [bit_to_flip, bitstream[bit_to_flip]]
            bitstream[bit_to_flip] = not bitstream[bit_to_flip]
            self.error_bit_index = bit_to_flip 
            print(f"Bit {bit_to_flip} corrupted (excluding identifier).")
            self.error_type = "bit_error"

    #stuff error 
    def corrupt_stuff(self):
        bitstream = self.get_bitstream()
        identifier_length = 11 
        start_of_corruptible_bits = identifier_length + 2

        if len(bitstream) > start_of_corruptible_bits + 5:
            for i in range(start_of_corruptible_bits, len(bitstream) - 6):
                if len(set(bitstream[i:i + 5])) == 1:
                    stuffing_bit = bitstream[i] 
                    bitstream.insert(i + 5, stuffing_bit)  
                    self.error_bit_index = i + 5  
                    print(f"Bit stuffing error injected at index {i + 5} (excluding identifier).")
                    self.error_type = "stuff_error"
                    return 
            
            print("No valid position for bit stuffing error found.")
        else:
            print("Bitstream too short for bit stuffing error.")

    #crc error
    def corrupt_crc(self):
        print(f"CRC before: {self.crc}")
        self.crc ^= 0x1  
        print(f"CRC after: {self.crc}")
        self.error_type = "crc_error"
        self.error_bit_index = len(self.get_bitstream()) - 16

    #ack error
    def corrupt_ack(self): 
        self.ack_slot = 1
        self.error_bit_index = self.get_ack_index()
        self.error_type = "ack_error"

    #form error
    def corrupt_form(self): 
        self.end_of_frame = [0] * 7  
        self.error_bit_index = len(self.get_bitstream()) - 10
        self.error_type = "form_error"

    def calculate_bit_pos(self):
        pos = 0
        positions = {}

        if isinstance(self, DataFrame) or isinstance(self, RemoteFrame):
            positions["SOF"] = pos
            pos += 1

            positions["ID"] = pos
            pos += 11

            positions["RTR"] = pos
            pos += 1
             
            positions["CONTROL"] = pos
            pos += 6

            data_length = (len(self.data_field) * 8) if self.data_field else 0
            if data_length > 0:
                positions["DATA"] = pos
                pos += data_length

            positions["CRC"] = pos
            pos += 15

            positions["CRC_DELIM"] = pos
            pos += 1

            positions["ACK"] = pos
            pos += 1

            positions["ACK_DELIM"] = pos
            pos += 1

            positions["EOF"] = pos
            pos += 7

        elif isinstance(self, ErrorFrame):
            positions["ERROR_FLAG"] = pos
            pos += 6

            positions["ERROR_DELIM"] = pos
            pos += 8

        elif isinstance(self, OverloadFrame):
            positions["OVERLOAD_FLAG"] = pos
            pos += 6

            positions["OVERLOAD_DELIM"] = pos
            pos += 8

        return positions
    
class DataFrame(CANMessage):
    def __init__(self, identifier, sent_by, data):
        super().__init__(identifier, sent_by, data, frame_type="Data")

class RemoteFrame(CANMessage):
    def __init__(self, identifier, sent_by):
        super().__init__(identifier, sent_by, data=None, frame_type="Remote")

class ErrorFrame(CANMessage):
    def __init__(self, sent_by):
        super().__init__(sent_by=sent_by, identifier=None, data=None, frame_type="Error")
        self.error_flag = [0] * 6 
        self.error_delimiter = [1] * 8

    def get_bitstream(self):
        return self.error_flag + self.error_delimiter

    def __repr__(self):
        return "ErrorFrame(error_flag={}, error_delimiter={})".format(self.error_flag, self.error_delimiter)

class OverloadFrame(CANMessage):
    def __init__(self, sent_by):
        super().__init__(sent_by=sent_by, identifier=None, data=None, frame_type="Overload")
        self.overload_flag = [0] * 6  
        self.overload_delimiter = [1] * 8 

    def get_bitstream(self):
        return self.overload_flag + self.overload_delimiter

    def __repr__(self):
        return f"OverloadFrame(overload_flag={self.overload_flag}, overload_delimiter={self.overload_delimiter})"
 