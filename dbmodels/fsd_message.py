class FsdMessage:
    """Represents a private message sent over the FSD protocol, received over our API."""

    def __init__(self, token: str, timestamp: int, sender: str, receiver: str, message: str):
        """

        :param token:       Registration token
        :param timestamp:   When the message was received by the VATSIM/IVAO client, in milliseconds since Unix epoch
        :param sender:      Callsign of sender
        :param receiver:    Callsign of receiver
        :param message:     Contents of received message
        """
        self.token = token
        self.timestamp = timestamp
        self.sender = sender
        self.receiver = receiver
        self.message = message
