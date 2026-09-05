import re

with open('app/build.gradle', 'r') as f:
    text = f.read()

text = re.sub(r'applicationId ".*?"', 'applicationId "com.noishixzen.kupido2"', text)

with open('app/build.gradle', 'w') as f:
    f.write(text)
