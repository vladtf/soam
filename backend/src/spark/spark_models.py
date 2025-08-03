"""Spark-related data models."""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class SparkWorker:
    """Model for Spark worker information."""
    id: str
    host: str
    port: int
    webuiaddress: str
    cores: int
    coresused: int
    coresfree: int
    memory: int
    memoryused: int
    memoryfree: int
    resources: Dict[str, Any]
    resourcesused: Dict[str, Any]
    resourcesfree: Dict[str, Any]
    state: str
    lastheartbeat: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SparkWorker':
        """Create SparkWorker instance from dictionary data."""
        return cls(
            id=data["id"],
            host=data["host"],
            port=data["port"],
            webuiaddress=data["webuiaddress"],
            cores=data["cores"],
            coresused=data["coresused"],
            coresfree=data["coresfree"],
            memory=data["memory"],
            memoryused=data["memoryused"],
            memoryfree=data["memoryfree"],
            resources=data.get("resources", {}),
            resourcesused=data.get("resourcesused", {}),
            resourcesfree=data.get("resourcesfree", {}),
            state=data["state"],
            lastheartbeat=data["lastheartbeat"]
        )


@dataclass
class SparkApplication:
    """Model for Spark application information."""
    id: str
    starttime: int
    name: str
    cores: int
    user: str
    memoryperexecutor: int
    memoryperslave: int
    resourcesperexecutor: List[Dict[str, Any]]
    resourcesperslave: List[Dict[str, Any]]
    submitdate: str
    state: str
    duration: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SparkApplication':
        """Create SparkApplication instance from dictionary data."""
        return cls(
            id=data["id"],
            starttime=data["starttime"],
            name=data["name"],
            cores=data["cores"],
            user=data["user"],
            memoryperexecutor=data.get("memoryperexecutor", 0),
            memoryperslave=data.get("memoryperslave", 0),
            resourcesperexecutor=data.get("resourcesperexecutor", []),
            resourcesperslave=data.get("resourcesperslave", []),
            submitdate=data["submitdate"],
            state=data["state"],
            duration=data["duration"]
        )


@dataclass
class SparkMasterStatus:
    """Model for Spark master status response."""
    url: str
    workers: List[SparkWorker]
    aliveworkers: int
    cores: int
    coresused: int
    memory: int
    memoryused: int
    resources: List[Dict[str, Any]]
    resourcesused: List[Dict[str, Any]]
    activeapps: List[SparkApplication]
    completedapps: List[SparkApplication]
    activedrivers: List[Dict[str, Any]]
    completeddrivers: List[Dict[str, Any]]
    status: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SparkMasterStatus':
        """Create SparkMasterStatus instance from dictionary data."""
        # Parse workers
        workers = [SparkWorker.from_dict(worker_data) for worker_data in data.get("workers", [])]
        
        # Parse applications
        active_apps = [SparkApplication.from_dict(app_data) for app_data in data.get("activeapps", [])]
        completed_apps = [SparkApplication.from_dict(app_data) for app_data in data.get("completedapps", [])]
        
        return cls(
            url=data["url"],
            workers=workers,
            aliveworkers=data.get("aliveworkers", 0),
            cores=data["cores"],
            coresused=data["coresused"],
            memory=data["memory"],
            memoryused=data["memoryused"],
            resources=data.get("resources", []),
            resourcesused=data.get("resourcesused", []),
            activeapps=active_apps,
            completedapps=completed_apps,
            activedrivers=data.get("activedrivers", []),
            completeddrivers=data.get("completeddrivers", []),
            status=data["status"]
        )
