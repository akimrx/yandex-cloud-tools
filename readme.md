# Yandex Cloud Tools
**Simple snapshots tool for [Yandex.Cloud](https://cloud.yandex.com)**

**Required Python 3.6+**

#### Create-snapshots
Automatically create snapshots for VM from config file (only boot-disks). Sequence for running instances: stop VM – create snapshot – start VM, for stopped instances just create snapshot.

#### Delete-snapshots
Automatic deletion of snapshots older than N days for instances from config. 
The lifetime is specified in the config file.

# Get started
## Install submodules
`pip install -r requirements.txt`

## Get OAuth-token
* [Get token here](https://oauth.yandex.com/authorize?response_type=token&client_id=1a6990aa636648e9b2ef855fa7bec2fb)

### Edit config file
* Create config dir `mkdir -p ~/.ya-tools`
* Edit `vim ydnx.cfg.example`
* Insert OAuth-token into config file.
* Enter instance ID into config file. For multiple instances enter space separated IDs (without the quotes).
* Enter snapshots lifetime in days.
* Move file `mv yndx.cfg.example ~/.ya-tools/yndx.cfg`
Example config file:
```
[Auth]
OAuth_token = AQAAAAYqwerty1qwerty2qwerty3

[Instances]
# Space separated instance IDs
IDs = efqwer2tyu3qwert7yz ef1xzcvbnm2qwerty1qwe

[Snapshots]
# Specify the lifetime of snapshots in days
Lifetime = 14
```

# Usage
```
akimrx@thinkpad:~/github/yandex-cloud-tools$ ./snaps.py --help
usage: snaps.py [-h] [-v] [-c] [-d] [-f]

Snapshots-tools. To work, you must add instances id to the config file (space separated if multiple)

optional arguments:
  -h, --help     show this help message and exit
  -v, --version  show program's version number and exit
  -c, --create   create snapshots for VMs
  -d, --delete   delete all old snapshots for instances
  -f, --full     create snapshots and delete old snapshots for instances
  --async        use this arg only if disks count <= 15 (active-operations-count limit)


```

# Shedule with Cron
You can run the script manually as needed, or create a task in the scheduler [Cron](https://help.ubuntu.com/community/CronHowto). 

