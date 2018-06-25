import jsonrpcclient
import ipaddress
import argparse

import pprint
import json
from datetime import datetime

import asyncio
from jsonrpc_async import Server


def fetch_peers(ip, jrpc_port):
    json_rpc_url = "http://{}:{}".format(ip, jrpc_port)
    print("calling {}".format(json_rpc_url))
    peers = jsonrpcclient.request(json_rpc_url, "getPeers")
    return ['{}:{}'.format(ipaddress.ip_address(int(p['ip'], 16)), int(p['port'], 16))
            for p in peers['peers']]


'''
given ip and p2p_port, jrpc_port, recursively crawl the p2p network
assumes (jrpc_port-p2p_port) are the same across all peers
looks up peer ip from ip_map, allowing this code to be run from outside network

NOTE: run from within EC2 if you do not have ip_lookup
'''


def crawl_recursive(cache, ip, p2p_port, jrpc_port, ip_lookup={}):
    ip = ip_lookup[ip] if ip in ip_lookup else ip
    key = '{}:{}'.format(ip, p2p_port)
    if key in cache:
        return
    cache[key] = fetch_peers(ip, jrpc_port)
    for peer in cache[key]:
        peer_ip, peer_p2p_port = peer.split(':')
        crawl_recursive(cache, peer_ip, int(peer_p2p_port), int(peer_p2p_port) + jrpc_port - p2p_port, ip_lookup)


# returns json_rpc_port
def find_all_clusters(ip, p2p_port, jrpc_port, ip_lookup={}):
    cache = {}
    crawl_recursive(cache, ip, p2p_port, jrpc_port, ip_lookup)
    return ["{}:{}".format(c.split(':')[0], int(c.split(':')[1]) + jrpc_port - p2p_port) for c in cache.keys()]


def fetch_range(ip, jrpc_port_start, p2p_port_start, num):
    return {'{}:{}'.format(ip, p2p_port_start + i): fetch_peers(ip, jrpc_port_start + i) for i in range(num)}


def json_topoplogy_d3(ip, p2p_port, jrpc_port, ip_lookup={}):
    cache = {}
    crawl_recursive(cache, ip, p2p_port, jrpc_port, ip_lookup)
    nodes = []
    ids = {}
    d3_id = 1
    for key, val in cache.items():
        nodes.append({
            'name': key,
            'label': '',
            'id': d3_id
        })
        ids[key] = d3_id
        d3_id += 1
    links = []
    for key, val in cache.items():
        for target in val:
            for x, y in ip_lookup.items():
                target = target.replace(x, y)
            links.append({
                "source": ids[key],
                "target": ids[target],
                "type": "PEER",
            })
    print(json.dumps({'nodes': nodes, 'links': links}))


def print_all_clusters(ip, p2p_port, jrpc_port, ip_lookup={}):
    pprint.pprint(find_all_clusters(ip, p2p_port, jrpc_port, ip_lookup))


async def async_stats(idx, server):
    response = await server.getStats()
    print("idx={};pendingTxCount={}".format(idx, response['pendingTxCount']))


async def async_watch(clusters):
    servers = [(idx, Server("http://{}".format(cluster))) for idx, cluster in enumerate(clusters)]
    while True:
        await asyncio.gather(*[async_stats(idx, server) for (idx, server) in servers])
        print('... as of {}'.format(datetime.now()))
        await asyncio.sleep(1)


def watch_network_stats(ip, p2p_port, jrpc_port, ip_lookup={}):
    clusters = find_all_clusters(ip, p2p_port, jrpc_port, ip_lookup)
    print("=======================IDX MAPPING=======================")
    pprint.pprint(["idx={};host:json={}".format(idx, cluster) for idx, cluster in enumerate(clusters)])
    asyncio.get_event_loop().run_until_complete(async_watch(clusters))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip", default='54.186.3.84', type=str)
    parser.add_argument(
        "--jrpc_port", default=48491, type=int)
    parser.add_argument(
        "--p2p_port", default=48291, type=int)
    parser.add_argument(
        "--command", default="print_all_clusters", type=str)
    parser.add_argument(
        "--ip_lookup", default='{"172.31.15.196": "54.186.3.84"}', type=str)
    args = parser.parse_args()

    globals()[args.command](args.ip, args.p2p_port, args.jrpc_port, json.loads(args.ip_lookup))


if __name__ == '__main__':
    main()
