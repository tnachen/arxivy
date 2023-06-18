#+++++++++++++++++++++++++++++++++++++++++++++++#
#                                               #
#   MAKEFILE                                    #
#   --------                                    #
#                                               #
#   Contains commands for setting up a          #
#   development environment, linting,           #
#   running test, and packaging.                #
#                                               #
#   - develop:    creates a development         #
#                 environment using `venv`.     #
#                                               #
#   - test:       runs all tests with py.test   #
#                 and reports coverage.         #
#                                               #
#   - build:      builds docker images, CLI,    #
#                 and the web UI.               #
#                                               #
#   - clean:      cleans build directory.       #
#                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++#
magenta="\\033[34m"
reset="\\033[0m"
green="\\033[32m"
yellow="\\033[33m"
cyan="\\033[36m"
white="\\033[37m"

all: develop

develop:
	@printf "${white}\n[1/1] > ${magenta}Creating local development environment ...${reset} \n";
	if [ ! -d "venv" ]; then python3 -m venv venv; venv/bin/pip install pip --upgrade; venv/bin/pip install -r requirements.txt; fi;

	@printf "${white}\n> ${green}Python virtual env setup successfully.${reset}";
	@printf "${white}> Activate it with: ${reset}\n";
	@printf "${white}     source venv/bin/activate ${reset} \n";
