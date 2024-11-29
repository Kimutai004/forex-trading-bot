import unittest
import logging

def run_tests():
    # Suppress logging output during tests
    logging.getLogger().setLevel(logging.CRITICAL)

    # Discover all tests in the 'tests' directory
    loader = unittest.TestLoader()
    suite = loader.discover('tests')

    # Open a file to write the test results
    with open('test_results.txt', 'w') as f:
        # Create a test runner that writes to the file
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        result = runner.run(suite)

if __name__ == '__main__':
    run_tests()
