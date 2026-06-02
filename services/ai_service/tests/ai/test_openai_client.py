from app.openai_client import OpenAIClient


def test_response_input_uses_output_text_for_assistant_messages() -> None:
    messages = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Second question"},
    ]

    payload_input = OpenAIClient()._input(messages, attachments=None, attachment_groups=None)

    assert payload_input == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "First question"}],
        },
        {
            "role": "assistant",
            "content": [{"type": "output_text", "text": "First answer"}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "Second question"}],
        },
    ]
