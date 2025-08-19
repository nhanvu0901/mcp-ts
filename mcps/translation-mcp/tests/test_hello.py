"""Hello unit test module."""

from translation.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello translation"
