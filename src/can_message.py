import random

class CANMessage:
    def __init__(self, identifier, sent_by, data=None, frame_type="Data", error_type=None):
        self.start_of_frame = [0]
        self.identifier = identifier
        self.frame_type = frame_type
        self.rtr = [0] if frame_type == "Data" else [1]
        self.control_field = self.calculate_control_field(data)
        self.data_field = data if data else [] 
        self.crc = self.calculate_crc()
        self.crc_delimiter = [1]
        self.ack_slot = 1
        self.ack_delimiter = [1]
        self.end_of_frame = [1] * 7
        self.intermission = [1] * 3
        self.error_type = error_type
        self.sender_id = sent_by
        self.bit_flipped = [None, None]
        self.error_bit_index = None
        self.transmitted_bitstream = None 
        self.retransmit_error = True
        self.unstuff_bitstream = None
        self.sections = {}

    def calculate_control_field(self, data):
        data_length_code_bits = "0000"
        if data:
            data_length_code = min(len(data), 8) 
            data_length_code_bits = f"{data_length_code:04b}"
        else:
            bytes_nr = random.randint(1, 8)
            #it should know for the data length code for the message it is requesting
            data_length_code_bits = f"{bytes_nr:04b}"
            #for a data frame message with that id we should request this number of bytes
        ide_bit = "0"
        reserved_bit = "0"
        control_field = data_length_code_bits + ide_bit + reserved_bit 

        return control_field

    def calculate_crc(self):
        if self.identifier is None:
            return 0

        # 0x4599 (binary: 100010010000001)
        polynomial = 0b100010010000001
        crc_register = 0 

        bitstream = (
            self.start_of_frame +
            [int(b) for b in f"{self.identifier:011b}"] +
            self.rtr +
            [int(b) for b in self.control_field]
        )

        if self.data_field:
            for byte in self.data_field:
                bitstream.extend([int(b) for b in f"{byte:08b}"])

        for bit in bitstream:
            crc_register = ((crc_register << 1) | bit) & 0x7FFF 

            if (crc_register & 0x4000): 
                crc_register ^= polynomial

        return crc_register

    def apply_bit_stuffing(self, bitstream):
        stuffed_bits = []
        consecutive_bits = 1
        stuffed_indices = []

        stuffed_bits.append(bitstream[0])

        for i in range(1, (len(bitstream) - 1)):
            bit = bitstream[i]

            if bit == stuffed_bits[-1]:
                consecutive_bits += 1
            else:
                consecutive_bits = 1

            stuffed_bits.append(bit)

            if consecutive_bits == 5:  #stuff bit after 5 consecutive bits
                stuff_bit = 1 - bit
                stuffed_bits.append(stuff_bit)
                stuffed_indices.append(len(stuffed_bits) - 1) 
                consecutive_bits = 1
            
        return stuffed_bits, stuffed_indices

    def get_bitstream(self):
        if self.transmitted_bitstream is not None:
            return self.transmitted_bitstream.copy() 

        bitstream = []

        bitstream.extend(self.start_of_frame)

        self.sections["id_start"] = len(bitstream)
        if self.identifier is not None:
            identifier_bits = [int(b) for b in f"{self.identifier:011b}"]
            bitstream.extend(identifier_bits)

        self.sections["rtr_start"] = len(bitstream)
        bitstream.extend(self.rtr)

        self.sections["control_start"] = len(bitstream)
        control_field_bits = [int(b) for b in self.control_field]
        bitstream.extend(control_field_bits)

        self.sections["data_start"] = len(bitstream)
        if self.data_field:
            for byte in self.data_field:
                byte_bits = [int(b) for b in f"{byte:08b}"]
                bitstream.extend(byte_bits)

        self.sections["crc_start"] = len(bitstream)
        crc_bits = [int(b) for b in f"{self.crc:015b}"]
        self.sections["crc_end"] = len(bitstream) + 15
        bitstream.extend(crc_bits)
        bitstream.extend(self.crc_delimiter)
        bitstream.append(self.ack_slot)
        bitstream.extend(self.ack_delimiter)
        bitstream.extend(self.end_of_frame)
        bitstream.extend(self.intermission)
        self.unstuff_bistream = bitstream.copy()

        end_stuff = self.sections["crc_end"] + 1
        stuffing_section = bitstream[1:end_stuff] 
        stuff_idx = None
        if self.error_type != "stuff_error":
            stuffed_section, stuff_idx = self.apply_bit_stuffing(stuffing_section)
            bitstream = [bitstream[0]] + stuffed_section + bitstream[-13:]

            offsets = self.compute_section_offsets(stuff_idx, self.sections)
            for key, offset in offsets.items():
                self.sections[key] += offset

        self.sections["crc_end"] = len(bitstream) - 13

        transmitted_bitstream = bitstream.copy()
        return bitstream.copy()
    
    def compute_section_offsets(self, stuffed_indices, sections):
        offsets = {}
        for section_name, start_idx in sections.items():
            inserted_before_this = sum(1 for pos in stuffed_indices if pos < start_idx)
            offsets[section_name] = inserted_before_this
        return offsets

    def get_ack_index(self):
        # base_length = 1 + 11 + 1 + 6 + 15 + 1  #not doing this bc of the bit stuffing
        # data_length = 8 * len(self.data_field)
        # ack_index = base_length + data_length 
        ack_index = (len(self.get_bitstream()) - 1) - 11
        return ack_index

    def update_ack(self):
        self.ack_slot = 0

    def __repr__(self):
        if self.identifier is not None:
            return (f"CANMessage(type={self.frame_type}, id={self.identifier}, data={self.data_field}, "
                    f"crc={self.crc}, rtr={self.rtr}), ack_slot={self.ack_slot}")
        else:
            return f"CANMessage(type={self.frame_type})"

    def corrupt_bit(self):
        bitstream = self.get_bitstream()
        identifier_length = 1 + 11 
        start_of_corruptible_bits = identifier_length + 1 + 6 

        max_corrupt_bit = 1 + 11 + 1 + 6 + (8 * len(self.data_field)) + 15 - 1 

        if len(bitstream) > start_of_corruptible_bits and start_of_corruptible_bits < max_corrupt_bit:
            bit_to_flip = random.randint(start_of_corruptible_bits, max_corrupt_bit)
            original_bit = bitstream[bit_to_flip]
            bitstream[bit_to_flip] = 1 - bitstream[bit_to_flip] 
            self.bit_flipped = [bit_to_flip, original_bit]
            self.error_bit_index = bit_to_flip 
            self.error_type = "bit_error"
            print(f"Bit {bit_to_flip} corrupted (excluding identifier).")

            self.transmitted_bitstream = bitstream.copy()
        else:
            print("No valid position for bit corruption found or bitstream too short.")

    def corrupt_stuff(self):
        bitstream = self.get_bitstream()[:] 
        identifier_length = 1 + 11 
        start_of_corruptible_bits = identifier_length + 1 + 6 
        flat_bitstream = bitstream[1:-13] 
        self.error_type = "stuff_error"

        bytes_in_data = len(self.data_field)
        random_byte = random.randint(0, bytes_in_data - 1)
        self.data_field[random_byte] = 63

        i = 1
        #verify if there are 6 consecutive bits that are the same and keep track of the index of the last bit
        while i < len(self.get_bitstream()) - 18:
            print(f"{i}: {self.get_bitstream()[i]}")
            if self.get_bitstream()[i] == self.get_bitstream()[i + 1] == self.get_bitstream()[i + 2] == self.get_bitstream()[i + 3] == self.get_bitstream()[i + 4] == self.get_bitstream()[i + 5]:
                self.error_bit_index = i + 5
                #print(f"Stuff error at index {self.error_bit_index}.")
                break
            i += 1

        self.transmitted_bitstream = self.get_bitstream().copy()

    def corrupt_crc(self):
        self.crc ^= 0x1  
        self.error_type = "crc_error"
        self.error_bit_index = self.get_crc_bit_index() + 14 
        print(f"CRC error injected by flipping bit at index {self.error_bit_index}.")

        bitstream = self.get_bitstream()
        if len(bitstream) >= self.error_bit_index +1:
            bitstream[self.error_bit_index] = 1 - bitstream[self.error_bit_index]
            self.transmitted_bitstream = bitstream.copy()
        else:
            print("Bitstream too short to inject CRC error.")

    def corrupt_ack(self):
        self.ack_slot = 1
        self.error_bit_index = self.get_ack_index()
        self.error_type = "ack_error"
        print(f"ACK error injected at index {self.error_bit_index}.")

        bitstream = self.get_bitstream()
        if len(bitstream) > self.error_bit_index:
            bitstream[self.error_bit_index] = 1
            self.transmitted_bitstream = bitstream.copy()
        else:
            print("Bitstream too short to inject ACK error.")

    def corrupt_form(self):
        self.end_of_frame = [0] * 7  
        self.error_type = "form_error"
        self.error_bit_index = len(self.get_bitstream()) - 10
        print(f"Form error injected by invalidating EOF at index {self.error_bit_index}.")

        self.update_ack()
        bitstream = self.get_bitstream()
        print(f"{bitstream}")
        for i in range(7):
            if len(bitstream) > self.error_bit_index + i:
                bitstream[self.error_bit_index + i] = 0
        self.transmitted_bitstream = bitstream.copy()

    def get_crc_bit_index(self):
        return 1 + 11 + 1 + 6 

    def get_eof_bit_index(self):
        return 1 + 11 + 1 + 6 + (8 * len(self.data_field)) + 15 + 1 + 1 + 1 + 7
    
    def get_bitstream_length(self):
        return len(self.get_bitstream())

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

# if __name__=="__main__":
    #testing stuffing
    # message = DataFrame(516, 1, [0x01, 0x02])
    # bitstream = message.get_bitstream()
    
    # #sections of the message
    # print(f"Sections: {message.sections}")
    # print(f"bitstream length: {len(bitstream)}")

    # message = DataFrame(516, 1, [0x01, 0x02])
    # corrupted_message = message.corrupt_form()