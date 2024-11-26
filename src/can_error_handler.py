from can_message import CANMessage, DataFrame, ErrorFrame, OverloadFrame, RemoteFrame

class CANErrorHandler:
    def inject_error(self, error_type, message):
        if isinstance(message, ErrorFrame) or isinstance(message, OverloadFrame):
            print(f"Cannot inject errors into {message.frame_type}.")
            return

        valid_errors = {
            "Data": ["bit_error", "stuff_error", "crc_error", "ack_error", "form_error"],
            "Remote": ["bit_error", "stuff_error", "ack_error", "form_error"],
        }

        if error_type in valid_errors.get(message.frame_type, []):
            getattr(message, f"corrupt_{error_type.split('_')[0]}")()  #calling corrupt method according to the error we want to inject
            print(f"{error_type} injected into message ID {message.identifier}.")
        else:
            print(f"{error_type} is not valid for {message.frame_type}.")


    def bit_stuffing_check(self, bitstream):
        consecutive_count = 1
        last_bit = bitstream[0]
        for bit in bitstream[1:]:
            if bit == last_bit:
                consecutive_count += 1
                if consecutive_count > 5:
                    return True 
            else:
                consecutive_count = 1
            last_bit = bit
        return False

    def crc_check(self, message, computed_crc):
        return message.crc != computed_crc

    def frame_check(self, message):
        return len(message.end_of_frame) != 7 or any(bit != 1 for bit in message.end_of_frame)

    def bit_monitoring_check(self, transmitted_bit, bus_bit):
        return transmitted_bit != bus_bit

    def acknowledgement_check(self, message):
        return message.ack_slot != 0 
    
    def detect_error(self, error_type, message):
        if error_type == "bit_error":
            return message.error_type == "bit_error"
        elif error_type == "stuff_error":
            return message.error_type == "stuff_error"
        elif error_type == "crc_error":
            return message.error_type == "crc_error"
        elif error_type == "ack_error":
            return message.error_type == "ack_error"
        elif error_type == "form_error":
            return message.error_type == "form_error"
        return False
