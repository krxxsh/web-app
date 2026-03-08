import uuid

def create_virtual_meeting(appointment):
    """
    Simulates or integrates with a virtual meeting provider.
    For MVP, we use Jitsi Meet (Open Source, no API key required for basic use).
    """
    if not appointment.service.is_virtual:
        return None

    meeting_id = str(uuid.uuid4())[:12]
    # Standard Jitsi Meet URL format
    virtual_url = f"https://meet.jit.si/AISched-{meeting_id}"

    appointment.virtual_link = virtual_url
    return virtual_url
