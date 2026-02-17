# hft_trade



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/user/project/repository/web_editor/#create-a-file) or [upload](https://docs.gitlab.com/user/project/repository/web_editor/#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/ai_generated_codes/hft_trade.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.com/ai_generated_codes/hft_trade/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/user/project/merge_requests/creating_merge_requests/)
* [Automatically close issues from merge requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/topics/autodevops/requirements/)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ci/environments/protected_environments/)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.

## Mock Order Book Data Generator

This project includes a Python script to generate mock order book update data for simulating crypto trading scenarios without network access.

### Features
- Generates continuous *delta* order book updates for BTC/USDT, ETH/USDT, XRP/USDT, ADA/USDT (only changed portions, mimicking real API feeds).
- Each update: time (float Unix timestamp), symbol, bids (JSON array sorted descending by price), asks (JSON array sorted ascending by price; qty=0 indicates cancel/delete).
- Uses persistent per-symbol order books (bounded to ~20 levels/side) with random deltas (add/modify/delete) to prevent growth and simulate realistic cancellations.
- Price continuity via random walk (no jumps); higher frequency (~100-1000 updates/sec) suitable for crypto/HFT analysis.
- Fully configurable per-pair: tick sizes (e.g., 0.01 for BTC/ETH, 0.0001 for XRP/ADA), precisions (2 decimals for majors, 4 for alts), and relative offsets for logical scaling—no uniform treatment.
- Runs for 10 seconds; outputs to `order_book_updates.xlsx` (arrays as JSON for Excel compatibility).

### Setup Development Environment

To run the code, set up your Python environment as follows:

1. **Install Python**: Ensure Python 3.8+ is installed. Download from [python.org](https://www.python.org/downloads/) if needed. Verify with:
   ```
   python --version
   ```
   (On some systems, use `python3`.)

2. **Create Virtual Environment** (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # or
   venv\Scripts\activate  # On Windows
   ```

3. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```
   This installs `pandas` (for DataFrame and Excel export) and `openpyxl` (Excel engine).

No other dependencies or network access required. The script uses only standard library + these packages for mock data generation.

### Usage

Run the generator:
```
python generate_order_book_updates.py
```

- It will print progress and save/overwrite `order_book_updates.xlsx` in the current directory (now with improved per-pair realism).
- Customize: Edit `generate_order_book_updates(duration=10)` call for different run times, or tweak TICK_SIZES/PRECISIONS/VOLATILITIES dicts in the script.
- To use data: Load in Python with `pd.read_excel('order_book_updates.xlsx')`, then parse JSON: `df['bids'] = df['bids'].apply(json.loads)`. Deltas enable reconstructing full books incrementally.
- Inspect book state in code by extending the script if needed.

This provides high-fidelity simulation for your crypto analyzer app. Per-symbol configs (ticks, precision, etc.) are at the top of the script for easy tuning.

### Live Order Book GUI
New feature: `order_book_gui.py` visualizes the order book like a live depth book/table.

- Bids in green, asks in red.
- Replays deltas from `order_book_updates.xlsx` for streaming simulation.
- Shows top 10 levels/side with cumulative qty; per-symbol selector.
- Uses Tkinter (built-in) + pandas for simple, dependency-light display.

#### Usage
1. Generate data first: `python generate_order_book_updates.py`
2. Run GUI: `python order_book_gui.py`
   - Select symbol, click "Start Live Replay" to see updates flow in real-time.
   - Table auto-colors (bids green at top in ascending order, asks red at bottom in descending order per spec) and refreshes; cumuls logical from best levels.
   - Includes order execution/matching: crossed books (max bid >= min ask) auto-trade, preventing invalid states and simulating fills.

No extra deps (Tkinter is stdlib; assumes X11/display for Linux GUI). Extend for charts (e.g., add Matplotlib) if needed. Per-symbol precision respected in display.
