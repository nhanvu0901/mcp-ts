"""Hello unit test module."""

from document.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello document"
