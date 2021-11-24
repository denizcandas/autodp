# AutoDP (Automatic Defect Prediction)

The aim of AutoDP is to automatically detect and predict defects in GitHub
repositories. The tool uses a modified version of SZZ to detect defects and
predict the state of the target commit. Afterwards, it may suggest further
steps to lower the defect probability of the target commit.

### How to use

##### Manual testing

- Clone this repository
- Install requirements using pip install -r requirements.txt
- Use the .env.example file to create an .env file which has your information
- Run the main method
- The repository targets the head commit, but COMMIT_SHA variable allows the
  user to target an earlier commit

##### In a pipeline

- Clone this repository
- Install the requirements
- Set the environment variables TOKEN and REPOSITORY (optionally COMMIT_SHA),
  e.g. TOKEN=<your_token_here>, check out the .env.example for more variables
- Call the python script

### Original SZZ

The original SZZ uses a combination of issues and defect fixing commits to
locate defects. A commit is assumed to be defective if its contents have
been changed by the fix (which is located using git blame) and the date of
this defective change is earlier than the issue. Additional steps are taken
to ensure that an issue and a fix are actually connected.

### Modified SZZ

Currently, we do not confirm that an issue has been resolved by a fix.
Additionally, we use failing pipelines to locate extra defects. A commit which
has caused a pipeline to fail is considered to be defective, but if follow-up
pipelines are also failing, we only assume the first change is defective.

### Targets

- Use 1000 commits (currently the system sometimes fails to work with 500 commits)
- Reduce the running time to 5 minutes or less
- Add review, parallel work, pr label and cool-off variables to improve quality

### TODOs

- Add tests
- Add a docker image to speed up usage
- Use only the GitHub GraphQL API
- Add example usage for pipelines
- Add GitHub actions example
- Use some sort of saving mechanism to reduce calls and improve speed
- Call pull request endpoints for further variables (reviews) and suggestions
- Call issue endpoints to confirm defects
- Predict defects locally for a change before it is pushed (git hook?)
- Use cross project knowledge to enhance defect prediction
