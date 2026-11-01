# Contributing to DVR-Scan

DVR-Scan is developed in the open on GitHub, and contributions of all kinds are
welcome: bug reports, feature requests, documentation fixes, test videos that
reproduce a problem, and pull requests.

## Getting Help

 - **User Guide and Documentation**: https://www.dvr-scan.com/guide/ and
   https://www.dvr-scan.com/docs/
 - **FAQ**: https://www.dvr-scan.com/faq/
 - **Discussions**: https://github.com/Breakthrough/DVR-Scan/discussions for
   usage questions and general help
 - **Discord**: https://discord.gg/69kf6f2Exb for real-time chat

## Reporting Bugs

Open an issue using the *Bug or Issue Report* template at
https://github.com/Breakthrough/DVR-Scan/issues/new/choose. Please include:

 - the full command line you ran, with `--verbosity debug` added
 - the complete program output
 - your DVR-Scan version (`dvr-scan --version`), operating system, and how you
   installed DVR-Scan (pip, standalone build, Docker, ...)
 - where possible, a short video clip that reproduces the problem

Bugs that only occur on a particular video are much easier to fix when a sample
is attached, even a short trimmed excerpt.

## Requesting Features

Open an issue using the *Feature or Enhancement Request* template. Describe the
problem you are trying to solve first, then any proposed solution. Example media
showing the situation you want DVR-Scan to handle is very helpful.

## Submitting Changes

1. Fork the repository and create a branch for your change.
2. Install DVR-Scan in development mode:

       pip install -e ".[dev]"

3. Make your changes. Keep the source tree ASCII-only (see `scripts/check_ascii.py`).
4. Format and lint with ruff:

       python -m ruff format dvr_scan/ tests/
       python -m ruff check dvr_scan/ tests/

5. Run the test suite:

       python -m pytest tests

   Tests that exercise ffmpeg-based output modes require an `ffmpeg` binary on
   your `PATH` (or a copy in the repository root).

6. Open a pull request against the `main` branch describing what the change does
   and why. Reference any related issues.

For larger changes, please open an issue first to discuss the approach before
investing significant time.

## License

By contributing, you agree that your contributions will be licensed under the
BSD 2-Clause License that covers the project (see `LICENSE`).
