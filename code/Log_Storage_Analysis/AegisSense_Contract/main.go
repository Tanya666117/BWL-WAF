package main

import (
	"chainmaker/pb/protogo"
	"chainmaker/sandbox"
	"chainmaker/sdk"
	"encoding/json"
	"log"
	"strconv"
	"strings"
)

// AegisSenseLogContract 日志存证合约结构体
type AegisSenseLogContract struct{}

// LogData 单条日志数据结构（与JSON中字段一致）
type LogData struct {
	DocId       string `json:"doc_id"`       // 日志唯一标识
	LogHash     string `json:"log_hash"`     // 日志哈希
	StoragePath string `json:"storage_path"` // 链下存储路径
}

// InitContract 合约初始化
func (a *AegisSenseLogContract) InitContract() protogo.Response {
	return sdk.Success([]byte("AegisSense批量日志合约初始化成功"))
}

// MaxBatchSize 单次批量上链条数上限，避免单笔交易过大；evidence_full_data.json 需分批调用 AddBatchLog
const MaxBatchSize = 2000

// InvokeContract 方法分发入口
func (a *AegisSenseLogContract) InvokeContract(method string) protogo.Response {
	switch method {
	case "AddBatchLog": // 批量上链（传入 evidence_full_data.json 的数组或子数组，可多次调用覆盖全量）
		return a.AddBatchLog()
	case "AddLog": // 单条上链（兼容旧逻辑）
		return a.AddLog()
	case "QueryLogByDocId": // 按 doc_id 查询
		return a.QueryLogByDocId()
	case "QueryLogByLogHash": // 按 log_hash 查询
		return a.QueryLogByLogHash()
	default:
		return sdk.Error("无效的合约方法")
	}
}

// UpgradeContract 合约升级入口
func (a *AegisSenseLogContract) UpgradeContract() protogo.Response {
	return sdk.Success([]byte("AegisSense批量日志合约升级成功"))
}

// AddBatchLog 核心方法：接收 evidence_full_data.json 的日志数组（或子数组），批量上链；全量文件需分批调用（每批不超过 MaxBatchSize 条）
func (a *AegisSenseLogContract) AddBatchLog() protogo.Response {
	args := sdk.Instance.GetArgs()
	batchLogsStr := strings.TrimSpace(string(args["batch_logs"]))
	if batchLogsStr == "" {
		return sdk.Error("批量日志参数（batch_logs）不能为空")
	}

	var batchLogs []LogData
	if err := json.Unmarshal([]byte(batchLogsStr), &batchLogs); err != nil {
		return sdk.Error("批量日志反序列化失败: " + err.Error())
	}

	if len(batchLogs) > MaxBatchSize {
		return sdk.Error("单次上链条数不能超过 " + strconv.Itoa(MaxBatchSize) + "，当前 " + strconv.Itoa(len(batchLogs)) + " 条，请分批调用 AddBatchLog")
	}

	successCount := 0
	for idx, logData := range batchLogs {
		if logData.DocId == "" || logData.LogHash == "" || logData.StoragePath == "" {
			sdk.Instance.Infof("第%s条日志参数为空，跳过", strconv.Itoa(idx+1))
			continue
		}

		logJson, err := json.Marshal(logData)
		if err != nil {
			sdk.Instance.Infof("第%s条日志序列化失败: %v", strconv.Itoa(idx+1), err)
			continue
		}

		if err = sdk.Instance.PutStateFromKey(logData.DocId, string(logJson)); err != nil {
			sdk.Instance.Infof("第%s条日志上链失败: %v", strconv.Itoa(idx+1), err)
			continue
		}

		// 建立 log_hash -> doc_id 索引，便于按哈希查询
		hashKey := "hash:" + logData.LogHash
		if err = sdk.Instance.PutStateFromKey(hashKey, logData.DocId); err != nil {
			sdk.Instance.Infof("第%s条日志哈希索引写入失败: %v", strconv.Itoa(idx+1), err)
			// 主数据已写入，不因索引失败回滚
		}

		successCount++
		sdk.Instance.Infof("第%d条日志上链成功 | doc_id: %s", idx+1, logData.DocId)
	}

	resultMsg := "批量日志处理完成 | 成功上链: " + strconv.Itoa(successCount) + "条 | 本批总数: " + strconv.Itoa(len(batchLogs))
	return sdk.Success([]byte(resultMsg))
}

// AddLog 单条日志上链（兼容之前逻辑，同时写入哈希索引以支持按 log_hash 查询）
func (a *AegisSenseLogContract) AddLog() protogo.Response {
	args := sdk.Instance.GetArgs()
	docId := string(args["doc_id"])
	logHash := string(args["log_hash"])
	storagePath := string(args["storage_path"])

	if docId == "" || logHash == "" || storagePath == "" {
		return sdk.Error("单条日志参数不能为空（doc_id/log_hash/storage_path）")
	}

	logData := LogData{DocId: docId, LogHash: logHash, StoragePath: storagePath}
	logJson, _ := json.Marshal(logData)
	if err := sdk.Instance.PutStateFromKey(docId, string(logJson)); err != nil {
		return sdk.Error("单条日志上链失败: " + err.Error())
	}
	_ = sdk.Instance.PutStateFromKey("hash:"+logHash, docId)

	return sdk.Success([]byte("单条日志上链成功 | doc_id: " + docId))
}

// QueryLogByDocId 按 doc_id 查询单条日志
func (a *AegisSenseLogContract) QueryLogByDocId() protogo.Response {
	args := sdk.Instance.GetArgs()
	docId := strings.TrimSpace(string(args["doc_id"]))
	if docId == "" {
		return sdk.Error("查询参数 doc_id 不能为空")
	}

	logJson, err := sdk.Instance.GetStateFromKey(docId)
	if err != nil {
		return sdk.Error("日志查询失败: " + err.Error())
	}
	if logJson == "" {
		return sdk.Error("未找到该 doc_id 的日志: " + docId)
	}
	return sdk.Success([]byte(logJson))
}

// QueryLogByLogHash 按 log_hash 查询单条日志（通过哈希索引找到 doc_id 再取完整记录）
func (a *AegisSenseLogContract) QueryLogByLogHash() protogo.Response {
	args := sdk.Instance.GetArgs()
	logHash := strings.TrimSpace(string(args["log_hash"]))
	if logHash == "" {
		return sdk.Error("查询参数 log_hash 不能为空")
	}

	docId, err := sdk.Instance.GetStateFromKey("hash:" + logHash)
	if err != nil || docId == "" {
		return sdk.Error("未找到该 log_hash 对应的存证: " + logHash)
	}

	logJson, err := sdk.Instance.GetStateFromKey(docId)
	if err != nil || logJson == "" {
		return sdk.Error("按 doc_id 读取日志失败: " + docId)
	}
	return sdk.Success([]byte(logJson))
}

// main 合约启动入口
func main() {
	err := sandbox.Start(new(AegisSenseLogContract))
	if err != nil {
		log.Fatal("合约启动失败: ", err)
	}
}
