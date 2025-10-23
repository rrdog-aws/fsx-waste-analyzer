import json
import boto3
import datetime
import logging
import math
import os
from decimal import Decimal

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Helper function to handle Decimal serialization
def decimal_serializer(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError("Type not serializable")

def lambda_handler(event, context):
    """Lambda handler for FSx analysis"""
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        
        # Handle OPTIONS request for CORS
        if event and event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS,POST'
                },
                'body': json.dumps({'message': 'CORS enabled'})
            }
        
        # Configuration
        region = os.environ.get('REGION', 'eu-west-1')
        lookback_days = int(os.environ.get('LOOKBACK_DAYS', '3'))
        period = int(os.environ.get('PERIOD', '840'))  # 5 min
        pctl = int(os.environ.get('PCTL', '95'))  # percentile
        fsid = os.environ.get('FSID', '')  # optional: limit to one FS
        top_vols = int(os.environ.get('TOP_VOLS', '0'))  # 0 = all volumes; else top-N by size
        mb = 1048576
        cold_io_threshold = 0.01
        
        # Initialize clients
        fsx_client = boto3.client('fsx', region_name=region)
        cloudwatch = boto3.client('cloudwatch', region_name=region)
        pricing_client = boto3.client('pricing', region_name='us-east-1')

        # Time helpers
        def now_utc():
            return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
        def start_utc():
            return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ---------- Helper functions ----------

        def check_encryption(fsid):
            """Check if filesystem is encrypted"""
            try:
                response = fsx_client.describe_file_systems(FileSystemIds=[fsid])
                encrypted = response['FileSystems'][0].get('KmsKeyId')
                if not encrypted:
                    return {
                        "type": "warning",
                        "message": "File system is not encrypted. Review if encryption is required for compliance."
                    }
                return {
                    "type": "info",
                    "message": "File system is encrypted."
                }
            except Exception as e:
                logger.error(f"Error checking encryption for {fsid}: {str(e)}")
                return {
                    "type": "warning",
                    "message": f"Unable to check encryption status: {str(e)}"
                }

        def get_storage_cost(region):
            """Get FSx storage cost per GiB for region"""
            try:
                region_map = {
                    "eu-west-1": "EU (Ireland)",
                    "us-east-1": "US East (N. Virginia)",
                    "eu-central-1": "EU (Frankfurt)",
                    "ap-southeast-1": "Asia Pacific (Singapore)",
                    "ap-southeast-2": "Asia Pacific (Sydney)",
                    "ap-northeast-1": "Asia Pacific (Tokyo)"
                }
                
                response = pricing_client.get_products(
                    ServiceCode='AmazonFSx',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_map.get(region, region)},
                        {'Type': 'TERM_MATCH', 'Field': 'storageType', 'Value': 'SSD'},
                        {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'General Purpose'}
                    ]
                )
                
                for price in response['PriceList']:
                    price_data = json.loads(price)
                    if 'terms' in price_data and 'OnDemand' in price_data['terms']:
                        for rate in price_data['terms']['OnDemand'].values():
                            for dimension in rate['priceDimensions'].values():
                                if 'GB-Mo' in dimension['unit']:
                                    return float(dimension['pricePerUnit']['USD'])
                return 0.145  # Default price if not found
            except Exception as e:
                logger.error(f"Error getting storage cost for {region}: {str(e)}")
                return 0.145

        def get_io_usage_45d(fsid, volid):
            """Get IO usage over 45 days"""
            try:
                end_time = datetime.datetime.now(datetime.timezone.utc)
                start_time = end_time - datetime.timedelta(days=45)
                period = 300  # 5 minutes

                metrics = {}
                for metric in ["DataReadBytes", "DataWriteBytes"]:
                    response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/FSx',
                        MetricName=metric,
                        Dimensions=[
                            {'Name': 'FileSystemId', 'Value': fsid},
                            {'Name': 'VolumeId', 'Value': volid}
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=['Sum']
                    )
                    metrics[metric] = sorted([dp['Sum'] for dp in response['Datapoints']])
                return metrics
            except Exception as e:
                logger.error(f"Error getting 45-day IO usage for {fsid}/{volid}: {str(e)}")
                return None

        def get_tags(fsid):
            try:
                if not fsid:
                    return []
                response = fsx_client.describe_file_systems(FileSystemIds=[fsid])
                if response and 'FileSystems' in response and response['FileSystems']:
                    return response['FileSystems'][0].get('Tags', [])
            except Exception as e:
                logger.error(f"Error fetching tags for {fsid}: {str(e)}")
            return []

        def get_volume_tags(volid):
            try:
                if not volid:
                    return []
                response = fsx_client.describe_volumes(VolumeIds=[volid])
                if response and 'Volumes' in response and response['Volumes']:
                    return response['Volumes'][0].get('Tags', [])
            except Exception as e:
                logger.error(f"Error fetching tags for volume {volid}: {str(e)}")
            return []

        def get_fs_list():
            try:
                if fsid:
                    src = fsx_client.describe_file_systems(FileSystemIds=[fsid])
                else:
                    src = fsx_client.describe_file_systems()
                
                filesystems = []
                if src and 'FileSystems' in src:
                    for fs in src['FileSystems']:
                        if fs.get('FileSystemType') == 'ONTAP':
                            fs_version = fs.get('OntapConfiguration', {}).get('FileSystemTypeVersion', 'GEN_1')
                            if '1' in fs_version:
                                filesystems.append(fs)
                return filesystems
            except Exception as e:
                logger.error(f"Error getting filesystem list: {str(e)}")
                return []

        def get_svms(fsid):
            try:
                if not fsid:
                    return []
                response = fsx_client.describe_storage_virtual_machines(
                    Filters=[{'Name': 'file-system-id', 'Values': [fsid]}]
                )
                return response.get('StorageVirtualMachines', [])
            except Exception as e:
                logger.error(f"Error getting SVMs for {fsid}: {str(e)}")
                return []

        def get_vols(fsid):
            try:
                if not fsid:
                    return []
                response = fsx_client.describe_volumes(
                    Filters=[{'Name': 'file-system-id', 'Values': [fsid]}]
                )
                return response.get('Volumes', [])
            except Exception as e:
                logger.error(f"Error getting volumes for {fsid}: {str(e)}")
                return []

        def get_series(metric, fsid, volid):
            try:
                if not fsid or not volid:
                    return []
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/FSx',
                    MetricName=metric,
                    Dimensions=[
                        {'Name': 'FileSystemId', 'Value': fsid},
                        {'Name': 'VolumeId', 'Value': volid}
                    ],
                    StartTime=datetime.datetime.strptime(start_utc(), "%Y-%m-%dT%H:%M:%SZ"),
                    EndTime=datetime.datetime.strptime(now_utc(), "%Y-%m-%dT%H:%M:%SZ"),
                    Period=period,
                    Statistics=['Sum']
                )
                if response and 'Datapoints' in response:
                    datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
                    return [dp.get('Sum', 0) for dp in datapoints]
                return []
            except Exception as e:
                logger.error(f"Error getting metrics for {fsid}/{volid}: {str(e)}")
                return []

        def get_storage_efficiency_savings(fsid):
            try:
                if not fsid:
                    return 0
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/FSx',
                    MetricName='StorageEfficiencySavings',
                    Dimensions=[{'Name': 'FileSystemId', 'Value': fsid}],
                    StartTime=datetime.datetime.strptime(start_utc(), "%Y-%m-%dT%H:%M:%SZ"),
                    EndTime=datetime.datetime.strptime(now_utc(), "%Y-%m-%dT%H:%M:%SZ"),
                    Period=period,
                    Statistics=['Average']
                )
                if response and 'Datapoints' in response:
                    datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
                    if datapoints:
                        return datapoints[-1].get('Average', 0)
                return 0
            except Exception as e:
                logger.error(f"Error getting storage efficiency for {fsid}: {str(e)}")
                return 0

        def pct_calc(values, p):
            try:
                if not values:
                    return 0
                values = sorted(values)
                n = len(values) - 1
                r = n * (p / 100)
                lo = math.floor(r)
                hi = math.ceil(r)
                if lo == hi:
                    return values[lo]
                else:
                    return values[lo] + ((r - lo) * (values[hi] - values[lo]))
            except Exception as e:
                logger.error(f"Error calculating percentile: {str(e)}")
                return 0

        def p95_mb_s(fsid, volid, metric):
            try:
                series = get_series(metric, fsid, volid)
                mb_per_s = [(val / mb) / period for val in series]
                return pct_calc(sorted(mb_per_s), pctl)
            except Exception as e:
                logger.error(f"Error calculating MB/s for {fsid}/{volid}: {str(e)}")
                return 0

        def process_volume(vol, svms, fsid):
            try:
                vid = vol.get('VolumeId')
                svmid = vol.get('OntapConfiguration', {}).get('StorageVirtualMachineId', '')
                path = vol.get('OntapConfiguration', {}).get('JunctionPath', '-')
                sizegib = math.floor(vol.get('OntapConfiguration', {}).get('SizeInMegabytes', 0) / 1024)
                tier = vol.get('OntapConfiguration', {}).get('TieringPolicy', {}).get('Name', 'UNKNOWN')

                vol_tags = get_volume_tags(vid)
                formatted_vol_tags = [{'Key': t.get('Key',''), 'Value': t.get('Value','')} for t in vol_tags if t.get('Key') and t.get('Value')]
                svmname = next((svm.get('Name','') for svm in svms if svm.get('StorageVirtualMachineId') == svmid), '')

                r95 = p95_mb_s(fsid, vid, "DataReadBytes")
                w95 = p95_mb_s(fsid, vid, "DataWriteBytes")
                total_io = r95 + w95

                io_usage = get_io_usage_45d(fsid, vid)
                if io_usage:
                    long_term_io = {
                        "read_45d": sum(io_usage.get("DataReadBytes", [])) / (45 * 86400),
                        "write_45d": sum(io_usage.get("DataWriteBytes", [])) / (45 * 86400)
                    }
                else:
                    long_term_io = {"read_45d":0, "write_45d":0}

                logical_size = vol.get('OntapConfiguration', {}).get('StorageEfficiencyAttributes', {}).get('LogicalSizeInBytes', 0)
                physical_size = vol.get('OntapConfiguration', {}).get('StorageEfficiencyAttributes', {}).get('PhysicalSizeInBytes', 0)
                efficiency_ratio = logical_size / physical_size if physical_size>0 else 0

                vol_recommendations = []
                if sizegib < 10:
                    vol_recommendations.extend([
                        {"type":"info","message":f"Volume is small ({sizegib} GiB). Consider consolidating or deleting if unused to reduce costs."},
                        {"type":"separator","message":""}
                    ])
                if total_io < cold_io_threshold:
                    vol_recommendations.extend([
                        {"type":"warning","message":f"Volume has low IO ({total_io:.2f} MB/s). Consider reviewing lifecycle policies to archive or delete stale data."},
                        {"type":"separator","message":""}
                    ])
                if efficiency_ratio>0 and efficiency_ratio<1.5:
                    vol_recommendations.append({"type":"info","message":f"Storage efficiency ratio is low ({efficiency_ratio:.2f}). Consider enabling or tuning deduplication, compression, and compaction."})

                monthly_cost = get_storage_cost(region)*sizegib

                return {
                    "id": vid,
                    "svmid": svmid,
                    "svmname": svmname,
                    "path": path,
                    "size_gib": sizegib,
                    "tiering_policy": tier,
                    "tags": formatted_vol_tags,
                    "read_throughput_mbs": r95,
                    "write_throughput_mbs": w95,
                    "total_throughput_mbs": total_io,
                    "efficiency_ratio": f"{efficiency_ratio:.2f}" if efficiency_ratio>0 else "N/A",
                    "usage_percentage": (physical_size/(sizegib*1024*1024*1024))*100 if sizegib>0 else 0,
                    "monthly_cost_estimate": monthly_cost,
                    "long_term_io": long_term_io,
                    "recommendations": vol_recommendations
                }

            except Exception as e:
                logger.error(f"Error processing volume {vol.get('VolumeId','unknown')}: {str(e)}")
                return None

        def analyze_filesystems():
            try:
                fs_list = get_fs_list()
                results=[]
                if not fs_list:
                    results.append({
                        "fsid":"N/A",
                        "gen":"N/A",
                        "state":"N/A",
                        "deployment_type":"N/A",
                        "storage_gib":0,
                        "provisioned_gib":0,
                        "slack_gib":0,
                        "slack_percentage":0,
                        "throughput_capacity":0,
                        "total_read_throughput":0,
                        "total_write_throughput":0,
                        "total_throughput":0,
                        "storage_efficiency":"N/A",
                        "storage_efficiency_percentage":0,
                        "monthly_cost_estimate":0,
                        "encryption_status":{"type":"info","message":"No FSx filesystems found."},
                        "tags":[],
                        "volumes":[],
                        "recommendations":[{"type":"info","message":"No FSx filesystems found."}]
                    })
                    return results

                for fs in fs_list:
                    fsid_val = fs.get('FileSystemId')
                    if not fsid_val: continue

                    gen = fs.get('OntapConfiguration', {}).get('FileSystemTypeVersion','GEN_1')
                    state = fs.get('Lifecycle','UNKNOWN')
                    fs_gib = fs.get('StorageCapacity',0)
                    tp = fs.get('OntapConfiguration', {}).get('ThroughputCapacity',0)
                    deployment_type = fs.get('OntapConfiguration', {}).get('DeploymentType','Unknown')

                    encryption_status = check_encryption(fsid_val)
                    fs_tags_raw = get_tags(fsid_val)
                    formatted_fs_tags = [{'Key':t.get('Key',''),'Value':t.get('Value','')} for t in fs_tags_raw if t.get('Key') and t.get('Value')]

                    svms = get_svms(fsid_val)
                    vols = get_vols(fsid_val)
                    vol_results=[]
                    tot_r=0
                    tot_w=0
                    total_logical_bytes=0
                    total_physical_bytes=0

                    for vol in vols:
                        vol_data=process_volume(vol, svms, fsid_val)
                        if vol_data:
                            vol_results.append(vol_data)
                            tot_r+=vol_data['read_throughput_mbs']
                            tot_w+=vol_data['write_throughput_mbs']
                            logical_size=vol.get('OntapConfiguration', {}).get('StorageEfficiencyAttributes', {}).get('LogicalSizeInBytes',0)
                            physical_size=vol.get('OntapConfiguration', {}).get('StorageEfficiencyAttributes', {}).get('PhysicalSizeInBytes',0)
                            total_logical_bytes+=logical_size
                            total_physical_bytes+=physical_size

                    prov_gib=sum(vol.get('OntapConfiguration', {}).get('SizeInMegabytes',0) for vol in vols)/1024
                    prov_gib=math.floor(prov_gib)
                    slack_gib=max(0, fs_gib-prov_gib)
                    slack_pct=int((100*(slack_gib/fs_gib)) if fs_gib>0 else 0)
                    storage_efficiency_pct=((total_logical_bytes-total_physical_bytes)/total_logical_bytes*100) if total_logical_bytes>0 else 0
                    storage_efficiency_clamped="N/A" if storage_efficiency_pct>1000 else f"{storage_efficiency_pct:.2f}"

                    fs_recommendations=[]
                    if encryption_status and encryption_status['type']=='warning': fs_recommendations.append(encryption_status)
                    if slack_pct>80:
                        fs_recommendations.append({"type":"warning","message":f"Slack space is high (~{slack_pct}%). Consider resizing."})
                    elif slack_pct<5:
                        fs_recommendations.append({"type":"critical","message":f"Slack space is low (~{slack_pct}%). Consider increasing filesystem size."})

                    tot_all=tot_r+tot_w
                    if tot_all>tp:
                        target=max(128, math.ceil(tot_all*1.2))
                        fs_recommendations.append({"type":"critical","message":f"Throughput demand ({tot_all:.2f} MB/s) exceeds capacity ({tp} MB/s). Consider increasing to ~{target} MB/s."})

                    if storage_efficiency_pct<20:
                        fs_recommendations.append({"type":"info","message":f"Storage efficiency is low ({storage_efficiency_pct:.1f}%). Consider enabling features."})

                    monthly_cost=get_storage_cost(region)*fs_gib

                    fs_result={
                        "fsid":fsid_val,
                        "gen":gen,
                        "state":state,
                        "deployment_type":deployment_type,
                        "storage_gib":fs_gib,
                        "provisioned_gib":prov_gib,
                        "slack_gib":slack_gib,
                        "slack_percentage":slack_pct,
                        "throughput_capacity":tp,
                        "total_read_throughput":tot_r,
                        "total_write_throughput":tot_w,
                        "total_throughput":tot_all,
                        "storage_efficiency":storage_efficiency_clamped,
                        "storage_efficiency_percentage":storage_efficiency_pct,
                        "monthly_cost_estimate":monthly_cost,
                        "encryption_status":encryption_status,
                        "tags":formatted_fs_tags,
                        "volumes":vol_results,
                        "recommendations":fs_recommendations
                    }
                    results.append(fs_result)
                return results

            except Exception as e:
                logger.error(f"Error in analyze_filesystems: {str(e)}")
                return [{
                    "fsid":"N/A",
                    "volumes":[],
                    "recommendations":[{"type":"critical","message":f"Error analyzing filesystems: {str(e)}"}]
                }]

        analysis_results = analyze_filesystems()

        return {
            'statusCode':200,
            'headers':{
                'Content-Type':'application/json',
                'Access-Control-Allow-Origin':'*',
                'Access-Control-Allow-Headers':'*',
                'Access-Control-Allow-Methods':'GET,OPTIONS,POST'
            },
            'body':json.dumps({
                'timestamp':now_utc(),
                'results':analysis_results
            }, default=decimal_serializer)
        }

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode':500,
            'headers':{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'},
            'body':json.dumps({'error':str(e)})
        }
