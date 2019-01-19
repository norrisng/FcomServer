from discord import DMChannel


class UserRegistration:
    """Represents a Discord user in the registration DB"""

    def __init__(self,
                 last_updated: str,
                 token: str,
                 discord_id: int,
                 discord_name: str,
                 is_verified,
                 callsign: str,
                 channel_object: DMChannel,
                 user_agent: str=None):
        """

        :param last_updated:    When the registration record was last updated.
        :param token:           Token associated with the Discord user in the registration DB
        :param discord_id:      Discord Snowflake ID for the Discord user
        :param discord_name:    Display name of the Discord user, including the discriminator (e.g. username#001)
        :param is_verified:     Whether the registration is confirmed over the Message Forwarder API
        :param callsign:        Callsign that the user is logged into VATSIM/IVAO as
        :param channel_object:  The DMChannel associated with the Discord user
        :param user_agent:      User agent of the client ("FcomClient/x.y.z")
        """
        self.last_updated = last_updated
        self.token = token
        self.discord_id = discord_id
        self.discord_name = discord_name

        # MySQL doesn't have a bool type, so we have to convert 1/0 (T/F) into bool
        if is_verified == 0:
            self.is_verified = False
        elif is_verified == 1:
            self.is_verified = True
        else:
            self.is_verified = is_verified

        self.callsign = callsign
        self.channel_object = channel_object
        self.user_agent = user_agent
