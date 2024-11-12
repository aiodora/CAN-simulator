class CANErrorHandler:
    def __init__(self):
        self.error_count = {
            "bit_error": 0,
            "stuff_error": 0,
            "form_error": 0,
            "ack_error": 0,
            "crc_error": 0
        }

    def bit_monitoring(self, transmitted_bit, received_bit):
        if transmitted_bit != received_bit:
            print("Bit Monitoring Error detected.")
            self.error_count["bit_error"] += 1
            return True
        return False

    def bit_stuffing_check(self, bitstream):
        consecutive_count = 1
        last_bit = bitstream[0]

        for bit in bitstream[1:]:
            if bit == last_bit:
                consecutive_count += 1
                if consecutive_count > 5:
                    print("Bit Stuffing Error detected.")
                    self.error_count["stuff_error"] += 1
                    return True
            else:
                consecutive_count = 1
            last_bit = bit
        return False

    def frame_check(self, message):
        if message.crc_delimiter != 1 or message.ack_delimiter != 1 or len(message.end_of_frame) != 7 or len(message.intermission) != 3:
            print("Frame Error detected.")
            self.error_count["form_error"] += 1
        return True

    def acknowledgement_check(self, message):
        if message.ack_slot == 1:
            print("Acknowledgement Error detected.")
            self.error_count["ack_error"] += 1
            return True
        return False

    def crc_check(self, message, calculated_crc):
        if message.crc != calculated_crc:
            print("CRC Error detected.")
            self.error_count["crc_error"] += 1
            return True
        return False

    def report_errors(self):
        return self.error_count

    def inject_error(self, error_type, message):
        if error_type == "bit":
            message.data_field[0] ^= 0xFF 
        elif error_type == "stuff":
            message.data_field.extend([1] * 6) 
        elif error_type == "ack":
            message.ack_slot = 1 
        elif error_type == "crc":
            message.crc ^= 0x1
        elif error_type == "frame_check":
            message.crc_delimiter = 0 
            message.ack_delimiter = 0
            message.end_of_frame = [0] * 7
            message.intermission = [0] * 3