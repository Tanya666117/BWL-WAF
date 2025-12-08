package main

import (
	"chainmaker/pb/protogo"
	"chainmaker/sandbox"
	"chainmaker/sdk"
	"encoding/json"
	"log"
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

// InvokeContract 方法分发入口
func (a *AegisSenseLogContract) InvokeContract(method string) protogo.Response {
	switch method {
	case "AddBatchLog": // 批量上链方法（读取JSON中所有日志）
		return a.AddBatchLog()
	case "AddLog": // 单条上链方法（兼容之前逻辑）
		return a.AddLog()
	case "QueryLogByDocId": // 单条查询方法
		return a.QueryLogByDocId()
	default:
		return sdk.Error("无效的合约方法")
	}
}

// UpgradeContract 合约升级入口
func (a *AegisSenseLogContract) UpgradeContract() protogo.Response {
	return sdk.Success([]byte("AegisSense批量日志合约升级成功"))
}

// AddBatchLog 核心方法：接收`evidence_full_data.json`的日志数组，批量上链
func (a *AegisSenseLogContract) AddBatchLog() protogo.Response {
	// 1. 获取批量日志参数（`batch_logs`对应JSON文件的日志数组字符串）
	args := sdk.Instance.GetArgs()
	batchLogsStr := string(args["batch_logs"])
	if batchLogsStr == "" {
		msg := "批量日志参数（batch_logs）不能为空"
		sdk.Instance.Infof(msg)
		return sdk.Error(msg)
	}

	// 2. 将日志数组字符串反序列化为[]LogData
	var batchLogs []LogData
	err := json.Unmarshal([]byte(batchLogsStr), &batchLogs)
	if err != nil {
		msg := "批量日志反序列化失败: " + err.Error()
		sdk.Instance.Infof(msg)
		return sdk.Error(msg)
	}

	// 3. 循环处理每条日志，逐一上链
	successCount := 0
	for idx, logData := range batchLogs {
		// 3.1 单条日志参数校验
		if logData.DocId == "" || logData.LogHash == "" || logData.StoragePath == "" {
			msg := "第" + string(idx+1) + "条日志参数为空（doc_id/log_hash/storage_path）"
			sdk.Instance.Infof(msg)
			continue // 跳过无效日志，继续处理其他日志
		}

		// 3.2 序列化单条日志为JSON字符串
		logJson, err := json.Marshal(logData)
		if err != nil {
			msg := "第" + string(idx+1) + "条日志序列化失败: " + err.Error()
			sdk.Instance.Infof(msg)
			continue
		}

		// 3.3 以doc_id为键，存储到链上（避免重复）
		err = sdk.Instance.PutStateFromKey(logData.DocId, string(logJson))
		if err != nil {
			msg := "第" + string(idx+1) + "条日志上链失败: " + err.Error()
			sdk.Instance.Infof(msg)
			continue
		}

		successCount++
		sdk.Instance.Infof("第%d条日志上链成功 | doc_id: %s", idx+1, logData.DocId)
	}

	// 4. 返回批量处理结果
	resultMsg := "批量日志处理完成 | 成功上链: " + string(successCount) + "条 | 总数: " + string(len(batchLogs))
	return sdk.Success([]byte(resultMsg))
}

// AddLog 单条日志上链（兼容之前逻辑）
func (a *AegisSenseLogContract) AddLog() protogo.Response {
	args := sdk.Instance.GetArgs()
	docId := string(args["doc_id"])
	logHash := string(args["log_hash"])
	storagePath := string(args["storage_path"])

	if docId == "" || logHash == "" || storagePath == "" {
		msg := "单条日志参数不能为空"
		sdk.Instance.Infof(msg)
		return sdk.Error(msg)
	}

	logData := LogData{DocId: docId, LogHash: logHash, StoragePath: storagePath}
	logJson, _ := json.Marshal(logData)
	err := sdk.Instance.PutStateFromKey(docId, string(logJson))
	if err != nil {
		return sdk.Error("单条日志上链失败: " + err.Error())
	}

	return sdk.Success([]byte("单条日志上链成功 | doc_id: " + docId))
}

// QueryLogByDocId 按doc_id查询日志
func (a *AegisSenseLogContract) QueryLogByDocId() protogo.Response {
	args := sdk.Instance.GetArgs()
	docId := string(args["doc_id"])
	if docId == "" {
		return sdk.Error("查询参数doc_id不能为空")
	}

	logJson, err := sdk.Instance.GetStateFromKey(docId)
	if err != nil {
		return sdk.Error("日志查询失败: " + err.Error())
	}
	if logJson == "" {
		return sdk.Error("未找到该doc_id的日志: " + docId)
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