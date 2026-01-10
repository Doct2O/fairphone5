#!/system/bin/sh
# set -x
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
  echo "Please DO NOT run as a root. The 'su' tool and root access is required, though."
  exit
fi

# Configuration variables
REQUESTED_MODE=""
SOCK_ADDR=""
SOCK_PORT=""

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

OPTIONS:
    --pty               Expose diag port via PTY (default)
    --sock <addr>:<port>
                        Expose diag port via socket of specified address and port
    --status            Check the current status of the diag-router-router.py script
    -h, --help          Show this help message

Only one of --pty, --sock, or --status can be used at a time.
If no arguments are provided, --pty mode is enabled by default.

DESCRIPTION:
    This script bootsrtaps start of the diag-router-router.py script and
    diag-router binary, to assert that they were launched properly and are talking to each other.
    Besides that it offers a much more approchable user interface and logic
    to switch the diag-router-router.py backend, utilizing --cmd argument of the pyhon's script.

EXAMPLES:
    $(basename "$0")
    $(basename "$0") --pty
    $(basename "$0") --status
    $(basename "$0") --sock 127.0.0.1:8080

EOF
}

################################################################################
# Parse command line arguments
################################################################################
parse_arguments() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                show_help
                exit 0
                ;;
            --pty)
                if [ -n "$REQUESTED_MODE" ]; then
                    echo "Error: --pty, --sock, and --status are mutually exclusive" >&2
                    exit 1
                fi
                REQUESTED_MODE="pty"
                shift
                ;;
            --status)
                if [ -n "$REQUESTED_MODE" ]; then
                    echo "Error: --pty, --sock, and --status are mutually exclusive" >&2
                    exit 1
                fi
                REQUESTED_MODE="status"
                shift
                ;;
            --sock)
                if [ -n "$REQUESTED_MODE" ]; then
                    echo "Error: --pty, --sock, and --status are mutually exclusive" >&2
                    exit 1
                fi
                REQUESTED_MODE="sock"

                # Verify that an argument is provided
                # grep '^-' checks if the next argument looks like a flag
                if [ -z "$2" ] || echo "$2" | grep -q '^-'; then
                    echo "Error: --sock requires an argument in format <addr>:<port>" >&2
                    exit 1
                fi

                # Parse the address:port format
                # Using standard grep regex: [^:] (not colon), * (any count), : (colon), [0-9]* (digits)
                if echo "$2" | grep -q '^[^:]*:[0-9][0-9]*$'; then
                    SOCK_ADDR=$(echo "$2" | cut -d: -f1)
                    SOCK_PORT=$(echo "$2" | cut -d: -f2)

                    # Validate that port is numeric (standard regex)
                    if [ -z "$SOCK_PORT" ] || ! echo "$SOCK_PORT" | grep -q '^[0-9][0-9]*$'; then
                        echo "Error: Invalid socket format. Expected <addr>:<port>" >&2
                        exit 1
                    fi

                    shift 2
                else
                    echo "Error: Invalid socket format. Expected <addr>:<port>" >&2
                    exit 1
                fi
                ;;
            *)
                echo "Error: Unknown argument '$1'" >&2
                echo "Use --help for usage information" >&2
                exit 1
                ;;
        esac
    done

    # Apply default mode if none was specified
    if [ -z "$REQUESTED_MODE" ]; then
        REQUESTED_MODE="pty"
    fi
}
parse_arguments "$@"

################################################################################
# Setup together platform's diag-router and diag-router-router.py
################################################################################

# Mount driver's diag endpoints
if ! su -c 'test -e /dev/ffs-diag/ep0' ; then
    su -c 'mkdir -p /dev/ffs-diag'
    su -c 'mount -t functionfs diag /dev/ffs-diag -o uid=2000,gid=1000,rmode=0770,fmode=0660,no_disconnect=1'
fi

ROUTER_ROUTER_RUN_CMD="python ${SCRIPT_DIR}/diag-router-router.py"

getDiagRouterSidePort() {(
    OUT=$(${ROUTER_ROUTER_RUN_CMD} --cmd status || exit 1) || exit 1
    echo "${OUT}" | head -n 1 | cut -d= -f2
)}
DIAG_ROUTER_SIDE_PORT="$(getDiagRouterSidePort)"
DRR_STATUS=$?
if test "${DRR_STATUS}" -ne 0 ; then
    # Python router script is guarded from being started twice in a daemon mode, so we don't need to check if it is already running
    echo "[*] Starting diag-router-router.py"
    nohup sh -c "${ROUTER_ROUTER_RUN_CMD}" >/dev/null 2>&1 &
    sleep 1

    echo "[*] Asking about status..."
    DIAG_ROUTER_SIDE_PORT=$(getDiagRouterSidePort)
    if  ! test -v DIAG_ROUTER_SIDE_PORT || test -z "${DIAG_ROUTER_SIDE_PORT}" ; then
        echo "[-] Could not communicate with the diag-router-router.py. Is it running? Is it listening for commands on default socket?"
        exit 1
    fi
    echo "[+] Status ok, diag-router side port: ${DIAG_ROUTER_SIDE_PORT}"
fi

isDiagRouterConnected() {
    [ "$(${ROUTER_ROUTER_RUN_CMD} --cmd status | head -n 2 | tail -n 1 | cut -d= -f2)" = "yes" ]
}
if ! [ -z "$(su -c 'pidof diag-router')" ] ; then
    IS_DIAG_ROUTER_CONNECTED=
    if ! isDiagRouterConnected ; then
        echo "[-] URECOREVALBE ERROR:"
        echo "    diag-router is already running, but is not connected to diag-router-router.py."
        echo "    This most likely is leftover from USB mode, or previous diag-router-router.py"
        echo "    was terminated. You'll need to reset the phone to get that working again."
        kill "$(lsof -t "${SCRIPT_DIR}/_diag-router-router.lock")" >/dev/null 2>&1
        exit 1
    fi
else
    echo "[*] diag-router not running, starting diag-router..."
    su -c "export LD_LIBRARY_PATH=\"${SCRIPT_DIR}\" ;
           nohup sh -c \"'${SCRIPT_DIR}/diag-router' -s 127.0.0.1:${DIAG_ROUTER_SIDE_PORT} &\" >/dev/null 2>&1 ;
           " </dev/null
    sleep 1
    if [ -z "$(su -c 'pidof diag-router')" ] ; then
        echo "[-] Failed to spawn diag-router"
        exit 1
    fi
    echo "[+] diag-router running"
    sleep 1
    if ! isDiagRouterConnected ; then
        echo "[-] URECOREVALBE ERROR: diag-router not connected to diag-router-router.py"
        exit 1
    else
        echo "[+] diag-router connected to diag-router-router.py"
    fi
fi

################################################################################
# Switch platform's diag-router-router.py backend if necessary
################################################################################
refreshBackendStatus() {
    STATUS=$(${ROUTER_ROUTER_RUN_CMD} --cmd status || exit 1)
    if ! test "$?" -eq 0 ; then
        echo "[-] Could not switch backend mode to $REQUESTED_MODE. Failed to get current status."
        exit 1
    fi
    BACKEND_MODE="$(echo "${STATUS}" | head -n 3 | tail -n 1 | cut -d= -f2)"
    BACKEND_INFO="$(echo "${STATUS}" | head -n 4 | tail -n 1 | cut -d= -f2)"
}
refreshBackendStatus
PTY_LINK_NAME="${SCRIPT_DIR}/ttyDiag"

case "$REQUESTED_MODE" in
    pty)
        makeTtyDiagLink(){
            if [ "${BACKEND_MODE}" = "pty" ] &&
               test -c "${BACKEND_INFO}" &&
               [ "$(readlink -f "${PTY_LINK_NAME}" >/dev/null)" !=  "${BACKEND_INFO}" ] ; then
                rm -f "${PTY_LINK_NAME}" >/dev/null && ln -s "${BACKEND_INFO}" "${PTY_LINK_NAME}"
            fi
        }
        makeTtyDiagLink
        if [ "${BACKEND_MODE}" = "pty" ] ; then
            echo "[*] Backend already in PTY mode, nothing to do."
            echo "    Use: ${SCRIPT_DIR}/ttyDiag -> ${BACKEND_INFO}"
            echo "    To access diag messages."
            exit 0
        elif [ "${BACKEND_MODE}" != "none" ] ; then
            echo "[*] Backend in mode '${BACKEND_MODE}', closing it first."
            if ! ${ROUTER_ROUTER_RUN_CMD} --cmd close > /dev/null ; then
                echo "[-] Closing backend failed."
                exit 1
            fi
            echo "[+] Previous backend closed."
        fi

        echo "[*] Switching to tty..."
        if ! ${ROUTER_ROUTER_RUN_CMD} --cmd pty >/dev/null ; then
            echo "[-] Switch failed."
            exit 1
        fi

        refreshBackendStatus
        BACKEND_MODE="${REQUESTED_MODE}"

        makeTtyDiagLink
        echo "[+] Switched, please use provided symlink:"
        echo "    '${PTY_LINK_NAME}'"
        echo "    to access diag messages."
        ;;
    sock)
        if [ "${BACKEND_MODE}" = "socket" ] &&
           [ "${BACKEND_INFO}" = "${SOCK_ADDR} ${SOCK_PORT}" ] ; then
            echo "[*] Backend already in socket mode, nothing to do."
            echo "    Connect to: ${SOCK_ADDR}:${SOCK_PORT}"
            echo "    To access diag messages."
            exit 0
        elif [ "${BACKEND_MODE}" != "none" ] ; then
            echo "[*] Backend in mode '${BACKEND_MODE}', closing it first."
            if ! ${ROUTER_ROUTER_RUN_CMD} --cmd close > /dev/null ; then
                echo "[-] Closing backend failed."
                exit 1
            fi
            echo "[+] Previous backend closed."
            rm -f "${PTY_LINK_NAME}"
        fi

        echo "[*] Switching to socket..."
        if ! ${ROUTER_ROUTER_RUN_CMD} --cmd "bind ${SOCK_ADDR} ${SOCK_PORT}" >/dev/null ; then
            echo "[-] Switch failed."
            exit 1
        fi
        echo "[+] Switched to socket"
        echo "    Connect to: ${SOCK_ADDR}:${SOCK_PORT}"
        echo "    To access diag messages."
    ;;
    status)
        if ! ${ROUTER_ROUTER_RUN_CMD} --cmd status ; then
             echo "[-] Failed to get status of diag-router-router.py."
            exit 1
        fi
    ;;
esac