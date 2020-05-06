# The Story

I was trying to migrate my data from one WD MyCloud EX 2 Ultra to another. This is my story of frustration, unanswered questions and a journey through bash + ssh.

## TL;DR

### Results

As of now, transfer speeds are consistently around 20-25 MB/s with the bottleneck being target drive write speed. Looking for possible causes.

### Takeaways

* To check for network performance, start with `iperf` for throughput, then `ethtool` for hardware layer and then proceed with tuning if necessary
* To check drive performance: `hdparm` and `dd` for read and write speeds, before checking transfer tools
* In this case, there is no performance difference between `scp` and `rsync`, athough if I wanted to resume broken copy process, rsync provides option to skip existing files (as a workaround in scp we can force this by removing write persmissions to already existing files)

## Initial conditions

| Parameter | Source | Target |
|-|-|-|
| Device | WD MyCloud EX2 Ultra | WD MyCloud EX2 Ultra |
| Firmware | 2.31.204 | 2.31.204 |
| Drives | 2 x 3 TB WDC WD30EFRX-68N32N0, FwRev=82.00A82 | 2 x 4 TB WDC WD40EFRX-68N32N0, FwRev=82.00A82 |
| Raid | Raid-1 | Raid-0 |
| Encrypted | No | Yes |
| IP address | 192.168.1.54 | 192.168.1.53 |

Connected using Cat 5E cables via TP-Link TL-SG108 Gigabit switch.

## Testing

First, I enabled ssh access in both NASes via web-ui:

```Settings > Network > SSH```

Default user for WD Mycloud EX2 Ultra is `sshd` so to connect to NAS I used command:

```ssh sshd@192.168.1.53```

To avoid multiple data transfers I logged into target ssh and tried to copy from source using `scp` command:

```
scp -rp sshd@192.168.1.54:/mnt/HD/HD_a2/Marcin /mnt/HD/HD_a2/
```

However, the transfer speed oscillated between 20-25 MB/s. This is way below expected 70 MB/s.

First I checked if network cards indeed connected using 1000 Mbps full-duplex using `ethtool`:

```
# ethtool egiga0
Settings for egiga0:
	Supported ports: [ TP MII ]
	Supported link modes:   10baseT/Half 10baseT/Full 
	                        100baseT/Half 100baseT/Full 
	                        1000baseT/Full 
	Supported pause frame use: No
	Supports auto-negotiation: Yes
	Advertised link modes:  10baseT/Half 10baseT/Full 
	                        100baseT/Half 100baseT/Full 
	                        1000baseT/Half 1000baseT/Full 
	Advertised pause frame use: No
	Advertised auto-negotiation: No
	Link partner advertised link modes:  10baseT/Half 10baseT/Full 
	                                     100baseT/Half 100baseT/Full 
	                                     1000baseT/Full 
	Link partner advertised pause frame use: No
	Link partner advertised auto-negotiation: Yes
	Speed: 1000Mb/s
	Duplex: Full
	Port: MII
	PHYAD: 0
	Transceiver: internal
	Auto-negotiation: on
	Link detected: yes
```

And that the IO and CPU are not saturated (those were already visible with web-ui, but I used `iostat`):

```
# iostat
Linux 3.10.39 (KlinkierChmurka) 	05/05/20 	_armv7l_	(2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
          29.23    6.16   28.23    1.36    0.00   35.02
```

```
# iostat -dx /dev/sda 5
Linux 3.10.39 (KlinkierChmurka) 	05/05/20 	_armv7l_	(2 CPU)

Device:         rrqm/s   wrqm/s     r/s     w/s    rkB/s    wkB/s avgrq-sz avgqu-sz   await r_await w_await  svctm  %util
sda               0.55     5.39    4.01   95.83   212.68 10755.40   219.70     0.45    4.53    4.82    4.52   1.19  11.90
```

I then checked if they are properly routing through the switch with `traceroute`:

```
# traceroute 192.168.1.54
traceroute to 192.168.1.54 (192.168.1.54), 30 hops max, 38 byte packets
 1  192.168.1.54 (192.168.1.54)  0.428 ms  0.428 ms  0.391 ms
 ```

Then I enabled jumbo frames in the web-ui and verified they are working using `ping`:

```
# ping -s 8972 192.168.1.54
PING 192.168.1.54 (192.168.1.54): 8972 data bytes
8980 bytes from 192.168.1.54: seq=0 ttl=64 time=0.898 ms
8980 bytes from 192.168.1.54: seq=1 ttl=64 time=2.904 ms
8980 bytes from 192.168.1.54: seq=2 ttl=64 time=0.786 ms
```

To do performance test I stopped the scp pressing `Ctrl-Z` (that would allow me to resume it later using `bg` of `fg`) and ran a network throughput test using `iperf`:

Source: 
```
# iperf -s
------------------------------------------------------------
Server listening on TCP port 5001
TCP window size: 85.3 KByte (default)
------------------------------------------------------------
[  4] local 192.168.1.53 port 5001 connected with 192.168.1.54 port 41261
[ ID] Interval       Transfer     Bandwidth
[  4]  0.0-10.0 sec  1.16 GBytes   991 Mbits/sec
```

Target:
```
# iperf -c 192.168.1.53
------------------------------------------------------------
Client connecting to 192.168.1.53, TCP port 5001
TCP window size: 93.3 KByte (default)
------------------------------------------------------------
[  3] local 192.168.1.54 port 41261 connected with 192.168.1.53 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0-10.0 sec  1.16 GBytes   992 Mbits/sec
```

This would rule out the network bottleneck. I decided to perform test on one large file using both `scp` and `rsync`, which can sometimes outperform `scp`.

```
# cd /mnt/HD/HD_a2/Marcin/
# dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 37.631790 seconds, 27.2MB/s
```

Starting with `scp`. Speed is consistent with what I obserwe with real data:
```
# scp -rp sshd@192.168.1.54:/mnt/HD/HD_a2/Marcin/1GB_TEST_FILE /mnt/HD/HD_a2/Marcin/1GB_TEST_FILE
sshd@192.168.1.54's password: 
1GB_TEST_FILE                 100% 1024MB  22.2MB/s   00:46 
```

Now `rsync`. Unfortunately, no improvement there:

```
# rsync -a sshd@192.168.1.54:/mnt/HD/HD_a2/Marcin/1GB_TEST_FILE /mnt/HD/HD_a2/Marcin/1GB_TEST_FILE --progress
sshd@192.168.1.54's password: 
receiving incremental file list
1GB_TEST_FILE
  1073741824 100%   21.57MB/s    0:00:47 (xfer#1, to-check=0/1)

sent 30 bytes  received 1073872980 bytes  20851903.11 bytes/sec
total size is 1073741824  speedup is 1.00
```

But wait, didn't the `dd` created the file on source NAS with speed around 27 MB/s? Time to bench the drives.

Source read speed:

```
# hdparm -t /dev/sda

/dev/sda:
Timing buffered disk reads: 538 MB in  3.01 seconds = 178.73 MB/sec
```

Target write speed:

```
# dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 41.367580 seconds, 24.8MB/s
```

Ok, so it would seem drive writing speed would be at fault. But why? SMB transfers to the drive are faster, 50-70 MB/s, close to advertised. And it would seem that I am not the only one with such problem (SCP slow, SMB fast):

* https://forums.freebsd.org/threads/slow-nfs-smb-afp-but-fast-scp-read-performance.68077/#post-410296

However, the benchmarks around web seem to find scp an rsync much faster than SMB:

* https://squarism.com/2010/02/12/scp-vs-rsync-vs-smb-vs-ftp/

Having depleted my theories I decided to ask WD community:

https://community.wd.com/t/wd-mycloud-ex2-ultra-2x4tb-slow-write-speeds-over-ssh/250988
