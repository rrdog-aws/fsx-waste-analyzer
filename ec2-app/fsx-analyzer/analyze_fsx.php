<?php
require '/path/to/aws/vendor/autoload.php';

use Aws\Fsx\FsxClient;
use Aws\CloudWatch\CloudWatchClient;
use Aws\Exception\AwsException;

// Enable error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Set CORS headers
header('Access-Control-Allow-Origin: *');
header('Content-Type: application/json');

try {
    // Initialize AWS clients
    $fsx = new FsxClient([
        'version' => 'latest',
        'region'  => 'us-east-1',
        'credentials' => [
            'key'    => 'YOUR_ACCESS_KEY',
            'secret' => 'YOUR_SECRET_KEY'
        ]
    ]);

    $cloudwatch = new CloudWatchClient([
        'version' => 'latest',
        'region'  => 'us-east-1',
        'credentials' => [
            'key'    => 'YOUR_ACCESS_KEY',
            'secret' => 'YOUR_SECRET_KEY'
        ]
    ]);

    // Get FSx systems
    $result = $fsx->describeFileSystems([]);
    $filesystems = $result['FileSystems'];
    
    $response = [];
    
    foreach ($filesystems as $fs) {
        if ($fs['FileSystemType'] === 'ONTAP') {
            // Get volumes
            $volumes = $fsx->describeVolumes([
                'Filters' => [
                    [
                        'Name' => 'file-system-id',
                        'Values' => [$fs['FileSystemId']]
                    ]
                ]
            ])['Volumes'];
            
            // Analyze volumes and collect metrics
            $total_volume_size = 0;
            $analyzed_volumes = [];
            
            foreach ($volumes as $vol) {
                $size_mb = $vol['OntapConfiguration']['SizeInMegabytes'];
                $size_gib = $size_mb / 1024;
                $total_volume_size += $size_gib;
                
                $analyzed_volumes[] = [
                    'id' => $vol['VolumeId'],
                    'size_gib' => $size_gib,
                    'read_throughput_mbs' => 0, // Add CloudWatch metrics if needed
                    'write_throughput_mbs' => 0
                ];
            }
            
            $slack = $fs['StorageCapacity'] - $total_volume_size;
            $slack_pct = ($slack / $fs['StorageCapacity']) * 100;
            
            // Generate recommendations
            $recommendations = [];
            if ($slack_pct > 80) {
                $recommendations[] = [
                    'type' => 'warning',
                    'message' => "High unused space ($slack_pct%). Consider reducing filesystem size."
                ];
            } elseif ($slack_pct < 5) {
                $recommendations[] = [
                    'type' => 'critical',
                    'message' => "Low free space ($slack_pct%). Consider increasing filesystem size."
                ];
            }
            
            $response[] = [
                'fsid' => $fs['FileSystemId'],
                'storage' => $fs['StorageCapacity'],
                'throughput' => $fs['OntapConfiguration']['ThroughputCapacity'],
                'total_volume_size' => $total_volume_size,
                'slack_space' => $slack,
                'slack_percentage' => $slack_pct,
                'volumes' => $analyzed_volumes,
                'recommendations' => $recommendations
            ];
        }
    }
    
    echo json_encode($response);
    
} catch (AwsException $e) {
    http_response_code(500);
    echo json_encode([
        'error' => $e->getMessage()
    ]);
}
?>

