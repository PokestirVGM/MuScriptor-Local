#!/bin/zsh
cd "${0:A:h}"
zsh tools/update.sh
result=$?
echo
if [[ $result -eq 0 ]]; then echo 'Update complete.'; else echo 'Update could not finish. See the message above.'; fi
echo 'Press Return to close.'
read
