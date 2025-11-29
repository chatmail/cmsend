# cmsend: chatmail sendmail tool for end-to-end encrypted messages  

To install use: 

    pip install cmsend 

To send and receive from a single chatmail relay: 

    cmsend --init nine.testrun.org   # <-- substitute with the domain you want to set as origin 

To setup a genesis chat using an invite link: 

    cmsend --join INVITELINK 

To send a message to the genesis chat: 

    echo "hello" | cmsend 

To send a message to the genesis chat with an attachment: 

    cmsend -m "here is the file" -a README.md

To show help:

    cmsend -h 


## Example outputs


## Developing / Releasing cmsend

1. clone the git repository at https://github.com/chatmail/cmsend 

2. install 'cmsend" in editing mode: `pip install -e .`

3. edit cmsend.py and test, finally commit your changes

4. set a new git-tag 

5. install build/release tools: `pip install build twine`

6. run the following command: 

        rm -rf dist && python -m build && twine upload -r pypi dist/cmsend*
