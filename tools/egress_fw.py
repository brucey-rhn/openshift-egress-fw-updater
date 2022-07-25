#!/usr/bin/python3

import argparse, copy, glob, json, os, ipaddress, subprocess, sys
from operator import ne


class CustomArgumentParser(argparse.ArgumentParser):
    class _CustomHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
        def _get_help_string(self, action):
            help = super()._get_help_string(action)
            if action.dest != 'help':
                help += ' [env: {}]'.format(action.dest.upper())
            return help

    def __init__(self, *, formatter_class=_CustomHelpFormatter, **kwargs):
        super().__init__(formatter_class=formatter_class, **kwargs)

    def _add_action(self, action):
        action.default = os.environ.get(action.dest.upper(), action.default)
        return super()._add_action(action)

def validate_ip_address(address):
    try:
        ip = ipaddress.ip_address(address)
#        print("IP address {} is valid. The object returned is {}".format(address, ip))
        return True
    except ValueError:
#        print("IP address {} is not valid".format(address))
        return False

def validate_ip_network(address):
    try:
        ip = ipaddress.ip_network(address)
#        print("IP address {} is valid. The object returned is {}".format(address, ip))
        return True
    except ValueError:
#        print("IP address {} is not valid".format(address))
        return False


parser = CustomArgumentParser(description='Generate OpenShift egress firewall rules for a project using EgressNetworkPolicy.')
parser.add_argument('-n', '--namespace', help="Namespace for EgressNetworkPolicy object")
parser.add_argument('-d', '--dir', help="The directory to search for *.allow files")
parser.add_argument('-o', '--output', choices=['json','yaml'], default='json', help="Output format for EgressNetworkPolicy declaration")
parser.add_argument('-w', '--write', help="Write output to file")
parser.add_argument('-g', '--glob', default='*.allow', help="Glob pattern for allow files")

args = parser.parse_args()
if not args.namespace:
    exit(parser.usage())

if not args.dir:
    args.dir = os.getcwd()

domain_files = glob.glob(os.path.join(args.dir, args.glob))

allow = {
    "to": {
        "cidrSelector": ''
    },
    "type": "Allow"
}
deny = {
    "to": {
        "cidrSelector": ''
    },
    "type": "Deny"
}
allow_all = {
    "to": {
        "cidrSelector": '0.0.0.0/0'
    },
    "type": "Allow"
}
deny_all = {
    "to": {
        "cidrSelector": '0.0.0.0/0'
    },
    "type": "Deny"
}

o = {
    "apiVersion": "network.openshift.io/v1",
    "kind": "EgressNetworkPolicy",
    "metadata": {
        "name": "default",
        "namespace": args.namespace
    },
    "spec": {
        "egress": []
    }
}

for f in domain_files:
    if f.endswith((".allow")):
        with open(f) as fp:
            for line in fp:
                l = line.strip()
                if ( l.startswith("#") or len(l.split()) == 0):
                    continue
                if( validate_ip_address(l)):
                    cidr = ipaddress.ip_network(l).with_prefixlen
                    allow['to']['cidrSelector'] = cidr
                    o['spec']['egress'].append(copy.deepcopy(allow))
                elif(validate_ip_network(l)):
                    cidr = ipaddress.ip_network(l).with_prefixlen
                    allow['to']['cidrSelector'] = cidr
                    o['spec']['egress'].append(copy.deepcopy(allow))
                else:
                    dig = subprocess.run(["dig", "+short", l ], encoding='utf-8', stdout=subprocess.PIPE)
                    ips = dig.stdout
                    for ip in ips.splitlines():
                        cidr = ipaddress.ip_network(ip).with_prefixlen
                        allow['to']['cidrSelector'] = cidr
                        o['spec']['egress'].append(copy.deepcopy(allow))
        o['spec']['egress'].append(deny_all)
    elif f.endswith((".deny")):
        with open(f) as fp:
            for line in fp:
                l = line.strip()
                if ( l.startswith("#") or len(l.split()) == 0):
                    continue
                if( validate_ip_address(l)):
                    cidr = ipaddress.ip_network(l).with_prefixlen
                    deny['to']['cidrSelector'] = cidr
                    o['spec']['egress'].append(copy.deepcopy(deny))
                elif(validate_ip_network(l)):
                    cidr = ipaddress.ip_network(l).with_prefixlen
                    deny['to']['cidrSelector'] = cidr
                    o['spec']['egress'].append(copy.deepcopy(deny))
                else:
                    dig = subprocess.run(["dig", "+short", l ], encoding='utf-8', stdout=subprocess.PIPE)
                    ips = dig.stdout
                    for ip in ips.splitlines():
                        cidr = ipaddress.ip_network(ip).with_prefixlen
                        deny['to']['cidrSelector'] = cidr
                        o['spec']['egress'].append(copy.deepcopy(deny))
        o['spec']['egress'].append(allow_all)

if args.write:
    out = open(args.write, 'w')
else:
    out = sys.stdout

if args.output == 'yaml':
    import yaml
    print(yaml.dump(o), file=out)
else:
    print(json.dumps(o), file=out)
