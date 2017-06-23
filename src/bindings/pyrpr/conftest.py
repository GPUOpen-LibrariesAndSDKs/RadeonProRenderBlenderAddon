"""
configuration for pytest-based tests
""" 

def pytest_addoption(parser):
    parser.addoption("--enable-cpu", action='store_true')
    parser.addoption("--enable-gpu", nargs='*', choices=range(8), type=int)
    parser.addoption("--pyrpr-log", action='store_true')

