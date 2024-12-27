import random

class CANMessage:
    def __init__(self, identifier, sent_by, data=None, frame_type="Data"):
        self.start_of_frame = [0]
        self.identifier = identifier
        self.frame_type = frame_type
        self.rtr = [0] if frame_type == "Data" else [1]
        self.control_field = self.calculate_control_field(data)
        self.data_field = data if data else []  # Up to 8 bytes
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
        self.transmitted_bitstream = None 

    def calculate_control_field(self, data):
        data_length_code = min(len(data), 8) if data else 0
        data_length_code_bits = f"{data_length_code:04b}"
        ide_bit = "0"
        reserved_bit = "0"
        control_field = data_length_code_bits + ide_bit + reserved_bit 
        return control_field

    def calculate_crc(self):
        if self.identifier is None:
            return 0

        # Standard CAN CRC-15 polynomial: 0x4599 (binary: 100010010000001)
        polynomial = 0b100010010000001
        crc_register = 0  # Initialize CRC register

        # Construct the bitstream up to the CRC field (excluding CRC itself)
        bitstream = (
            self.start_of_frame +
            [int(b) for b in f"{self.identifier:011b}"] +
            self.rtr +
            [int(b) for b in self.control_field]
        )

        # Append data field if present
        if self.data_field:
            for byte in self.data_field:
                bitstream.extend([int(b) for b in f"{byte:08b}"])

        # Perform CRC calculation using shift register method
        for bit in bitstream:
            # Shift CRC register left by 1 and input the current bit
            crc_register = ((crc_register << 1) | bit) & 0x7FFF  # Keep CRC register to 15 bits

            # If the leftmost bit (bit 14) is 1, XOR with the polynomial
            if (crc_register & 0x4000):  # 0x4000 is 1 << 14
                crc_register ^= polynomial

        # The CRC is the final value of the CRC register
        return crc_register

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
            if consecutive_bits == 6:  # Insert a stuff bit after 5 consecutive bits
                stuffed_bits.append(1 - last_bit)
                consecutive_bits = 0
            last_bit = bit
        stuffed_bits.append(last_bit)
        return stuffed_bits

    def get_bitstream(self):
        if self.transmitted_bitstream is not None:
            return self.transmitted_bitstream.copy()  # Return a copy to prevent accidental modifications

        bitstream = []

        # Start of Frame
        bitstream.extend(self.start_of_frame)

        # Identifier
        if self.identifier is not None:
            identifier_bits = [int(b) for b in f"{self.identifier:011b}"]
            bitstream.extend(identifier_bits)

        # RTR Bit
        bitstream.extend(self.rtr)

        # Control Field
        control_field_bits = [int(b) for b in self.control_field]
        bitstream.extend(control_field_bits)

        # Data Field
        if self.data_field:
            for byte in self.data_field:
                byte_bits = [int(b) for b in f"{byte:08b}"]
                bitstream.extend(byte_bits)

        # CRC Field
        crc_bits = [int(b) for b in f"{self.crc:015b}"]
        bitstream.extend(crc_bits)

        # CRC Delimiter
        bitstream.extend(self.crc_delimiter)

        # ACK Slot
        bitstream.append(self.ack_slot)

        # ACK Delimiter
        bitstream.extend(self.ack_delimiter)

        # End of Frame
        bitstream.extend(self.end_of_frame)

        # Intermission
        bitstream.extend(self.intermission)

        # Apply bit stuffing only to the SOF, Identifier, RTR, Control Field, Data Field, CRC Field
        # Exclude CRC Delimiter, ACK Slot, ACK Delimiter, EOF, and Intermission
        stuffing_section = bitstream[:-13]  # Exclude last 13 bits
        if self.error_type != "stuff_error":
            stuffed_section = self.apply_bit_stuffing(stuffing_section)
            # Combine stuffed section with the excluded parts
            bitstream = stuffed_section + bitstream[-13:]

        transmitted_bitstream = bitstream.copy()
        return bitstream.copy()

    def get_ack_index(self):
        # base_length = 1 + 11 + 1 + 6 + 15 + 1  # SOF + ID + RTR + Control + CRC + CRC Delimiter
        # data_length = 8 * len(self.data_field)
        # ack_index = base_length + data_length 
        ack_index = len(self.get_bitstream()) - 11
        return ack_index

    def update_ack(self):
        self.ack_slot = 0
        # No need to regenerate the bitstream here; it will be regenerated when get_bitstream is called

    def __repr__(self):
        if self.identifier is not None:
            return (f"CANMessage(type={self.frame_type}, id={self.identifier}, data={self.data_field}, "
                    f"crc={self.crc}, rtr={self.rtr}), ack_slot={self.ack_slot}")
        else:
            return f"CANMessage(type={self.frame_type})"

    # Error Injection Methods
    def corrupt_bit(self):
        bitstream = self.get_bitstream()
        identifier_length = 1 + 11  # SOF + Identifier
        start_of_corruptible_bits = identifier_length + 1 + 6  # RTR + Control Field

        # Ensure we don't corrupt CRC delimiter and beyond
        max_corrupt_bit = 1 + 11 + 1 + 6 + (8 * len(self.data_field)) + 15 - 1  # Up to CRC field

        if len(bitstream) > start_of_corruptible_bits and start_of_corruptible_bits < max_corrupt_bit:
            bit_to_flip = random.randint(start_of_corruptible_bits, max_corrupt_bit)
            original_bit = bitstream[bit_to_flip]
            bitstream[bit_to_flip] = 1 - bitstream[bit_to_flip]  # Flip the bit
            self.bit_flipped = [bit_to_flip, original_bit]
            self.error_bit_index = bit_to_flip 
            self.error_type = "bit_error"
            print(f"Bit {bit_to_flip} corrupted (excluding identifier).")

            # Update the transmitted_bitstream with the corrupted bitstream
            self.transmitted_bitstream = bitstream.copy()
        else:
            print("No valid position for bit corruption found or bitstream too short.")

    def corrupt_stuff(self):
        bitstream = self.get_bitstream()[:]  # Make a copy to modify
        identifier_length = 1 + 11  # SOF + Identifier
        start_of_corruptible_bits = identifier_length + 1 + 6  # RTR + Control Field
        flat_bitstream = bitstream[:-13]  # Exclude CRC Delimiter, ACK Slot, ACK Delimiter, EOF, and Intermission

        i = start_of_corruptible_bits
        while i <= len(flat_bitstream) - 5:
            if flat_bitstream[i:i + 5] == [flat_bitstream[i]] * 5:
                stuffing_bit = 1 - flat_bitstream[i] 
                flat_bitstream.insert(i + 5, stuffing_bit) 
                flat_bitstream[i + 5] = flat_bitstream[i]
                self.error_bit_index = i + 5
                self.error_type = "stuff_error"
                print(f"Bit stuffing error injected at index {i + 5}.")
                break
            else:
                i += 1 

        if self.error_type == "stuff_error":
            stuffed_section = flat_bitstream
            stuffed_bitstream = stuffed_section + bitstream[-13:]
            self.transmitted_bitstream = stuffed_bitstream.copy()
        else:
            print("No valid position for bit stuffing error found or bitstream too short.")

        self.transmitted_bitstream = self.get_bitstream().copy()

    def corrupt_crc(self):
        # Flip the least significant bit of CRC
        self.crc ^= 0x1  
        self.error_type = "crc_error"
        self.error_bit_index = self.get_crc_bit_index() + 14  # Assuming LSB is at the end
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
        self.error_bit_index = self.get_eof_bit_index()
        print(f"Form error injected by invalidating EOF at index {self.error_bit_index}.")

        bitstream = self.get_bitstream()
        for i in range(7):
            if len(bitstream) > self.error_bit_index + i:
                bitstream[self.error_bit_index + i] = 0
        self.transmitted_bitstream = bitstream.copy()

    def get_crc_bit_index(self):
        # Return the starting bit index of CRC field
        return 1 + 11 + 1 + 6  # SOF + Identifier + RTR + Control

    def get_eof_bit_index(self):
        # Return the starting bit index of EOF field
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
